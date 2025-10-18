How to generate and apply migrations
---

1. Install alembic:
    ```shell 
    pip install alembic
    ```
2. Initialize alembic:
    ```shell
    alembic init --package -t async database/migrations
    ```
   > The parameter `-t` is template.
   > If you use the asynchronous database driver, generate config by `async` template.
3. Change `env.py` and `alembic.ini` configuration files.
4. Generate migrations:
   ```shell
   alembic revision --autogenerate -m 'message'
   ```
5. Check migration and apply:
   ```shell
   alembic upgrade head
   ```
