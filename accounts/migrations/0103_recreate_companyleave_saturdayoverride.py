from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0102_delete_companyleave_delete_saturdayoverride'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS company_leaves (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    date date NOT NULL UNIQUE,
                    reason varchar(255) NOT NULL,
                    month int NOT NULL,
                    year int NOT NULL,
                    created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS saturday_overrides (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    date date NOT NULL UNIQUE,
                    status varchar(10) NOT NULL,
                    month int NOT NULL,
                    year int NOT NULL,
                    created_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                );
            """,
            reverse_sql="""
                DROP TABLE IF EXISTS company_leaves;
                DROP TABLE IF EXISTS saturday_overrides;
            """,
        ),
    ]
