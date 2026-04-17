from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0102_delete_companyleave_delete_saturdayoverride'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS company_leaves (
                    id bigserial PRIMARY KEY,
                    date date NOT NULL UNIQUE,
                    reason varchar(255) NOT NULL,
                    month int NOT NULL,
                    year int NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS saturday_overrides (
                    id bigserial PRIMARY KEY,
                    date date NOT NULL UNIQUE,
                    status varchar(10) NOT NULL,
                    month int NOT NULL,
                    year int NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT NOW(),
                    updated_at timestamptz NOT NULL DEFAULT NOW()
                );
            """,
            reverse_sql="""
                DROP TABLE IF EXISTS company_leaves;
                DROP TABLE IF EXISTS saturday_overrides;
            """,
        ),
    ]
