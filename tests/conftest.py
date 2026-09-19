"""Every test uses an isolated database, including assistant write tests."""
import os
import tempfile
from pathlib import Path

TEST_DIR=tempfile.TemporaryDirectory(prefix='pliz-tests-')
os.environ['DATABASE_URL']='sqlite:///'+(Path(TEST_DIR.name)/'test.db').as_posix()
os.environ['DBSTUDIOS_API_URL']=''
os.environ['DBSTUDIOS_API_KEY']=''
os.environ['OPENAI_API_KEY']=''

def pytest_sessionfinish(session,exitstatus):
    from backend.database import engine
    engine.dispose()
    TEST_DIR.cleanup()
