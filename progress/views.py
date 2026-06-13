from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Sum, Count, Q, Max
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from library.models import Surah, Verse
from community.models import LeaderBoard
from .models import UserProgress, ReadVerse, ReadingLog, UserSurahCompletion, Achievement, UserAchievement
from .serializers import UserProgressSerializer, UserAchievementSerializer

def ensure_default_achievements():
    achievements = [
        {"name": "First Surah", "description": "Completed your first Surah", "icon_name": "star", "points_bonus": 100},
        {"name": "100 Verses", "description": "Read a total of 100 verses", "icon_name": "trophy", "points_bonus": 50},
        {"name": "7 Day Streak", "description": "Read for 7 consecutive days", "icon_name": "fire", "points_bonus": 100},
        {"name": "100 Streak", "description": "Read for 100 consecutive days", "icon_name": "fire_gold", "points_bonus": 500},
        {"name": "Fast Climber", "description": "Gained 3 ranks on the leaderboard", "icon_name": "bolt", "points_bonus": 100},
        {"name": "Challenge Champion", "description": "Completed a weekly challenge", "icon_name": "crown", "points_bonus": 100},
    ]
    for ach in achievements:
        Achievement.objects.get_or_create(name=ach["name"], defaults=ach)

class UserProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ensure_default_achievements()
        user = request.user
        user_progress, _ = UserProgress.objects.get_or_create(user=user)
        
        # Period filtering: daily, weekly, monthly
        period = request.query_params.get('period', 'daily').lower()
        now = timezone.now()
        today = now.date()
        
        if period == 'weekly':
            period_start = today - timedelta(days=today.weekday())  # Monday
            prev_period_start = period_start - timedelta(days=7)
            prev_period_end = period_start
        elif period == 'monthly':
            period_start = today.replace(day=1)
            prev_period_end = period_start
            prev_period_start = (period_start - timedelta(days=1)).replace(day=1)
        else:  # daily
            period_start = today
            prev_period_start = today - timedelta(days=1)
            prev_period_end = today

        # 1. Period stats: Surahs Completed, Hours read, streak
        surahs_completed_count = UserSurahCompletion.objects.filter(
            user=user, completed_at__date__gte=period_start
        ).count()
        
        logs_in_period = ReadingLog.objects.filter(
            user=user, timestamp__date__gte=period_start
        )
        total_time_in_period = logs_in_period.aggregate(total=Sum('time_spent'))['total'] or timedelta(0)
        hours_read = round(total_time_in_period.total_seconds() / 3600.0, 2)
        
        # 2. Overall Progress (verses out of 6236)
        total_verses_read = ReadVerse.objects.filter(user=user).count()
        total_quran_verses = 6236
        completion_percentage = round((total_verses_read / total_quran_verses) * 100, 2) if total_quran_verses > 0 else 0
        
        # Growth calculation
        current_verses_count = ReadVerse.objects.filter(user=user, read_at__date__gte=period_start).count()
        prev_verses_count = ReadVerse.objects.filter(
            user=user, read_at__date__gte=prev_period_start, read_at__date__lt=prev_period_end
        ).count()
        
        if prev_verses_count > 0:
            growth = round(((current_verses_count - prev_verses_count) / prev_verses_count) * 100, 2)
        else:
            growth = 100.0 if current_verses_count > 0 else 0.0
            
        # 3. Activity Breakdown based on period
        today_logs = ReadingLog.objects.filter(user=user, timestamp__date=today)
        activity_slots = {}
        activity_label = ""
        today_total_minutes = round((today_logs.aggregate(total=Sum('time_spent'))['total'] or timedelta(0)).total_seconds() / 60.0, 1)

        if period == 'weekly':
            week_days = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
            time_slots = {day: timedelta(0) for day in week_days}
            period_logs = ReadingLog.objects.filter(user=user, timestamp__date__gte=period_start)
            for log in period_logs:
                day_name = week_days[log.timestamp.weekday()]
                time_slots[day_name] += log.time_spent
            activity_slots = {day: round(dur.total_seconds() / 60.0, 1) for day, dur in time_slots.items()}
            activity_label = f"You've read {hours_read} hours this week"
        elif period == 'monthly':
            weeks = ['W1', 'W2', 'W3', 'W4']
            time_slots = {w: timedelta(0) for w in weeks}
            period_logs = ReadingLog.objects.filter(user=user, timestamp__date__gte=period_start)
            for log in period_logs:
                day = log.timestamp.day
                if 1 <= day <= 7:
                    time_slots['W1'] += log.time_spent
                elif 8 <= day <= 14:
                    time_slots['W2'] += log.time_spent
                elif 15 <= day <= 21:
                    time_slots['W3'] += log.time_spent
                else:
                    time_slots['W4'] += log.time_spent
            activity_slots = {w: round(dur.total_seconds() / 60.0, 1) for w, dur in time_slots.items()}
            activity_label = f"You've read {hours_read} hours this month"
        else:
            time_slots = {
                '6AM': timedelta(0),
                '9AM': timedelta(0),
                '12PM': timedelta(0),
                '2PM': timedelta(0),
                '5PM': timedelta(0),
                '7PM': timedelta(0),
                'Now': timedelta(0)
            }
            for log in today_logs:
                hour = timezone.localtime(log.timestamp).hour
                if 5 <= hour < 8:
                    time_slots['6AM'] += log.time_spent
                elif 8 <= hour < 11:
                    time_slots['9AM'] += log.time_spent
                elif 11 <= hour < 13:
                    time_slots['12PM'] += log.time_spent
                elif 13 <= hour < 16:
                    time_slots['2PM'] += log.time_spent
                elif 16 <= hour < 18:
                    time_slots['5PM'] += log.time_spent
                elif 18 <= hour < 20:
                    time_slots['7PM'] += log.time_spent
                else:
                    time_slots['Now'] += log.time_spent
            activity_slots = {slot: round(dur.total_seconds() / 60.0, 1) for slot, dur in time_slots.items()}
            activity_label = f"You've read {today_total_minutes:.0f} minutes today"

        # 4. Recent Achievements
        earned_achievements = UserAchievement.objects.filter(user=user).select_related('achievement').order_by('-earned_at')
        achievements_data = UserAchievementSerializer(earned_achievements, many=True).data

        # 5. Monthly Goal (Complete 10 Surahs)
        month_start = today.replace(day=1)
        monthly_completions = UserSurahCompletion.objects.filter(user=user, completed_at__date__gte=month_start).count()
        monthly_goal_target = 10
        monthly_goal_percentage = min(round((monthly_completions / monthly_goal_target) * 100, 2), 100.0)

        # 6. Weekly Challenge (Read 50 verses)
        week_start = today - timedelta(days=today.weekday())
        weekly_verses_read = ReadVerse.objects.filter(user=user, read_at__date__gte=week_start).count()
        weekly_challenge_target = 50
        weekly_challenge_percentage = min(round((weekly_verses_read / weekly_challenge_target) * 100, 2), 100.0)
        
        # Award Challenge Champion achievement if they complete the weekly challenge
        if weekly_verses_read >= weekly_challenge_target:
            ch_ach = Achievement.objects.filter(name="Challenge Champion").first()
            if ch_ach:
                u_ach, created = UserAchievement.objects.get_or_create(user=user, achievement=ch_ach)
                if created:
                    user_progress.points += ch_ach.points_bonus
                    user_progress.save(update_fields=['points'])

        # 7. Continue Learning
        # Retrieve the 5 most recently read unique surahs from ReadingLog
        recent_surahs_query = (
            ReadingLog.objects.filter(user=user, surah__isnull=False)
            .values('surah')
            .annotate(last_read=Max('timestamp'))
            .order_by('-last_read')[:5]
        )
        recent_surah_ids = [item['surah'] for item in recent_surahs_query]
        surahs_map = {s.id: s for s in Surah.objects.filter(id__in=recent_surah_ids)}
        recent_surahs_ordered = [surahs_map[sid] for sid in recent_surah_ids if sid in surahs_map]

        recent_surahs_list = []
        for s in recent_surahs_ordered:
            read_count = ReadVerse.objects.filter(user=user, surah=s).count()
            recent_surahs_list.append({
                "id": s.id,
                "title": s.title,
                "english_name": s.english_name,
                "total_verses": s.total_verses,
                "verses_read": read_count,
            })

        # Fallback to defaults if list is empty
        if not recent_surahs_list:
            lrs = user_progress.last_read_surah
            if not lrs:
                lrs = Surah.objects.filter(id=67).first()
            if lrs:
                read_count = ReadVerse.objects.filter(user=user, surah=lrs).count()
                recent_surahs_list.append({
                    "id": lrs.id,
                    "title": lrs.title,
                    "english_name": lrs.english_name,
                    "total_verses": lrs.total_verses,
                    "verses_read": read_count,
                })
            else:
                recent_surahs_list.append({
                    "id": 67,
                    "title": "Surah Al-Mulk",
                    "english_name": "Al-Mulk",
                    "total_verses": 30,
                    "verses_read": 22,
                })

        recent_surah_data = recent_surahs_list[0] if recent_surahs_list else None

        completed_surah_data = None
        last_completion = UserSurahCompletion.objects.filter(user=user).select_related('surah').order_by('-completed_at').first()
        if last_completion:
            cs = last_completion.surah
            completed_surah_data = {
                "id": cs.id,
                "title": cs.title,
                "english_name": cs.english_name,
                "total_verses": cs.total_verses,
            }
        else:
            cs = Surah.objects.filter(id=1).first()
            if cs:
                completed_surah_data = {
                    "id": cs.id,
                    "title": cs.title,
                    "english_name": cs.english_name,
                    "total_verses": cs.total_verses,
                }
            else:
                completed_surah_data = {
                    "id": 1,
                    "title": "Surah Al-Fatihah",
                    "english_name": "Al-Fatihah",
                    "total_verses": 7,
                }

        response_data = {
            "period": period,
            "stats": {
                "surahs_completed": surahs_completed_count,
                "hours_read": hours_read,
                "streak": user_progress.reading_streak,
            },
            "overall_progress": {
                "verses_read": total_verses_read,
                "total_verses": total_quran_verses,
                "percentage": completion_percentage,
                "growth": f"+{growth}%" if growth >= 0 else f"{growth}%"
            },
            "activity_breakdown": {
                "slots": activity_slots,
                "label": activity_label
            },
            "recent_achievements": achievements_data,
            "monthly_goal": {
                "title": f"{today.strftime('%B')} Goal",
                "description": f"Complete {monthly_goal_target} Surahs",
                "current": monthly_completions,
                "target": monthly_goal_target,
                "percentage": monthly_goal_percentage
            },
            "weekly_challenge": {
                "title": "Weekly Challenge",
                "description": "Read 50 verses to climb up the ranks.",
                "points_reward": 100,
                "current": weekly_verses_read,
                "target": weekly_challenge_target,
                "percentage": weekly_challenge_percentage
            },
            "total_points": user_progress.points,
            "continue_learning": {
                "recent_surah": recent_surah_data,
                "recent_surahs": recent_surahs_list,
                "completed_surah": completed_surah_data,
            }
        }
        return Response(response_data)

    @swagger_auto_schema(request_body=UserProgressSerializer)
    def put(self, request):
        user_progress, _ = UserProgress.objects.get_or_create(user=request.user)
        serializer = UserProgressSerializer(user_progress, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

class LogReadingView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['surah_id', 'verse_start', 'verse_end', 'time_spent'],
            properties={
                'surah_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the Surah'),
                'verse_start': openapi.Schema(type=openapi.TYPE_INTEGER, description='First verse number read (1-indexed)'),
                'verse_end': openapi.Schema(type=openapi.TYPE_INTEGER, description='Last verse number read (1-indexed)'),
                'time_spent': openapi.Schema(type=openapi.TYPE_INTEGER, description='Time spent reading in seconds'),
            }
        )
    )
    def post(self, request):
        ensure_default_achievements()
        user = request.user
        surah_id = request.data.get('surah_id')
        verse_start = request.data.get('verse_start')
        verse_end = request.data.get('verse_end')
        time_spent_secs = request.data.get('time_spent')

        if not all([surah_id, verse_start, verse_end, time_spent_secs]):
            return Response({"error": "Missing parameters. surah_id, verse_start, verse_end, and time_spent are required."}, status=400)

        surah = get_object_or_404(Surah, id=surah_id)
        user_progress, _ = UserProgress.objects.get_or_create(user=user)

        # 1. Register ReadVerse objects and compute points
        new_verses_read = 0
        last_verse_obj = None
        for v_num in range(verse_start, verse_end + 1):
            try:
                verse = Verse.objects.get(surah=surah, verse_number=v_num)
                last_verse_obj = verse
                _, created = ReadVerse.objects.get_or_create(
                    user=user,
                    surah=surah,
                    verse=verse
                )
                if created:
                    new_verses_read += 1
                    user_progress.points += 1
            except Verse.DoesNotExist:
                pass

        # 2. Record ReadingLog
        ReadingLog.objects.create(
            user=user,
            surah=surah,
            verses_count=(verse_end - verse_start + 1),
            time_spent=timedelta(seconds=int(time_spent_secs))
        )

        # 3. Update UserProgress last read metadata
        if last_verse_obj:
            user_progress.last_read_surah = surah
            user_progress.last_read_verse = last_verse_obj

        # 4. Update Reading Streak
        today = timezone.now().date()
        if user_progress.last_reading_date == today - timedelta(days=1):
            user_progress.reading_streak += 1
        elif user_progress.last_reading_date == today:
            pass  # Streak already updated today
        else:
            user_progress.reading_streak = 1  # Streak reset or first reading
        user_progress.last_reading_date = today

        # Add time spent
        user_progress.total_time_spent += timedelta(seconds=int(time_spent_secs))
        user_progress.save()

        # 5. Check Surah completion and trigger achievements
        total_read_in_surah = ReadVerse.objects.filter(user=user, surah=surah).count()
        if total_read_in_surah >= surah.total_verses:
            completion, created = UserSurahCompletion.objects.get_or_create(
                user=user,
                surah=surah,
                defaults={'points_awarded': 100}
            )
            if created:
                user_progress.points += 100
                user_progress.save(update_fields=['points'])

                # Achievement: First Surah
                total_completions = UserSurahCompletion.objects.filter(user=user).count()
                if total_completions == 1:
                    ach = Achievement.objects.filter(name="First Surah").first()
                    if ach:
                        u_ach, a_created = UserAchievement.objects.get_or_create(user=user, achievement=ach)
                        if a_created:
                            user_progress.points += ach.points_bonus
                            user_progress.save(update_fields=['points'])

        # Achievement: 100 Verses
        total_unique_verses = ReadVerse.objects.filter(user=user).count()
        if total_unique_verses >= 100:
            ach = Achievement.objects.filter(name="100 Verses").first()
            if ach:
                u_ach, a_created = UserAchievement.objects.get_or_create(user=user, achievement=ach)
                if a_created:
                    user_progress.points += ach.points_bonus
                    user_progress.save(update_fields=['points'])

        # Achievement: 7 Day Streak
        if user_progress.reading_streak >= 7:
            ach = Achievement.objects.filter(name="7 Day Streak").first()
            if ach:
                u_ach, a_created = UserAchievement.objects.get_or_create(user=user, achievement=ach)
                if a_created:
                    user_progress.points += ach.points_bonus
                    user_progress.save(update_fields=['points'])

        # Achievement: 100 Streak
        if user_progress.reading_streak >= 100:
            ach = Achievement.objects.filter(name="100 Streak").first()
            if ach:
                u_ach, a_created = UserAchievement.objects.get_or_create(user=user, achievement=ach)
                if a_created:
                    user_progress.points += ach.points_bonus
                    user_progress.save(update_fields=['points'])

        # 6. Sync User points to Leaderboard entries
        LeaderBoard.objects.filter(user=user).update(points=user_progress.points, updated_at=timezone.now())

        return Response({
            "message": "Progress logged successfully",
            "verses_read_in_session": verse_end - verse_start + 1,
            "new_verses_read": new_verses_read,
            "points_earned": new_verses_read + (100 if (total_read_in_surah >= surah.total_verses and 'created' in locals() and created) else 0),
            "total_points": user_progress.points,
            "current_streak": user_progress.reading_streak
        })


class GlobalLeaderboardView(APIView):
    """Return all users sorted by points (descending) for the global leaderboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        for u in User.objects.filter(is_active=True):
            UserProgress.objects.get_or_create(user=u)

        entries = (
            UserProgress.objects
            .select_related('user')
            .order_by('-points')[:50]
        )
        results = []
        for entry in entries:
            user = entry.user
            photo_url = None
            if user.photo:
                photo_url = request.build_absolute_uri(user.photo.url)
            results.append({
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "photo": photo_url,
                },
                "points": entry.points,
                "reading_streak": entry.reading_streak,
            })
        return Response(results)
