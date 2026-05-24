from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("progress", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE progress_userprogress
                DROP CONSTRAINT IF EXISTS progress_userprogress_user_id_fec1b33d_fk_auth_user_id;

                ALTER TABLE progress_userprogress
                ADD CONSTRAINT progress_userprogress_user_id_fk
                FOREIGN KEY (user_id)
                REFERENCES users_user(id)
                DEFERRABLE INITIALLY DEFERRED;
            """,
            reverse_sql="""
                ALTER TABLE progress_userprogress
                DROP CONSTRAINT IF EXISTS progress_userprogress_user_id_fk;
            """
        ),
    ]
