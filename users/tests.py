from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from users.serializers import UserSerializer, UpdateProfileSerializer, RegisterSerializer

User = get_user_model()

class UserPhotoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpassword"
        )

    def test_photo_field_exists(self):
        self.assertFalse(self.user.photo)

    def test_photo_serialization(self):
        serializer = UserSerializer(instance=self.user)
        self.assertIn('photo', serializer.data)
        self.assertIsNone(serializer.data['photo'])

    def test_photo_update(self):
        # A tiny valid 1x1 pixel GIF file content
        image_content = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'
        uploaded_image = SimpleUploadedFile("avatar.gif", image_content, content_type="image/gif")

        serializer = UpdateProfileSerializer(instance=self.user, data={'photo': uploaded_image}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.photo)
        self.assertTrue(self.user.photo.name.startswith('profile_photos/avatar'))

    def test_registration_with_photo(self):
        image_content = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'
        uploaded_image = SimpleUploadedFile("reg_avatar.gif", image_content, content_type="image/gif")

        data = {
            'username': 'reguser',
            'email': 'reguser@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'photo': uploaded_image
        }
        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        self.assertIsNotNone(user.photo)
        self.assertTrue(user.photo.name.startswith('profile_photos/reg_avatar'))

    def test_registration_without_photo_fails(self):
        data = {
            'username': 'reguser2',
            'email': 'reguser2@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
        }
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('photo', serializer.errors)
