from django.db import migrations

def fix_user_fk_forward(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
                ALTER TABLE progress_userprogress
                DROP CONSTRAINT IF EXISTS progress_userprogress_user_id_fec1b33d_fk_auth_user_id;

                ALTER TABLE progress_userprogress
                ADD CONSTRAINT progress_userprogress_user_id_fk
                FOREIGN KEY (user_id)
                REFERENCES users_user(id)
                DEFERRABLE INITIALLY DEFERRED;
            """)

def fix_user_fk_backward(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
                ALTER TABLE progress_userprogress
                DROP CONSTRAINT IF EXISTS progress_userprogress_user_id_fk;
            """)

class Migration(migrations.Migration):

    dependencies = [
        ("progress", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(fix_user_fk_forward, fix_user_fk_backward),
    ]

