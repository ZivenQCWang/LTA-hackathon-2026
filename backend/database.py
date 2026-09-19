import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Text, Integer, Boolean, DateTime, select
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
(ROOT/'storage').mkdir(exist_ok=True)
URL=os.getenv('DATABASE_URL',f'sqlite:///{(ROOT/"storage"/"nightshift.db").as_posix()}')
if URL.startswith('postgres://'): URL=URL.replace('postgres://','postgresql+psycopg://',1)
elif URL.startswith('postgresql://'): URL=URL.replace('postgresql://','postgresql+psycopg://',1)
engine=create_engine(URL,connect_args={'check_same_thread':False} if URL.startswith('sqlite') else {},pool_pre_ping=True)
Session=sessionmaker(engine,expire_on_commit=False)
Base=declarative_base()

class Person(Base):
    __tablename__='nightshift_people'
    id=Column(String(40),primary_key=True,default=lambda:str(uuid.uuid4()))
    name=Column(String(120),nullable=False)
    role=Column(String(60),nullable=False)
    skills=Column(Text,nullable=False,default='track')
    max_shifts=Column(Integer,nullable=False,default=3)
    unavailable=Column(Text,nullable=False,default='')
    demo=Column(Boolean,nullable=False,default=False)
    active=Column(Boolean,nullable=False,default=True)

class Run(Base):
    __tablename__='nightshift_runs'
    id=Column(String(40),primary_key=True,default=lambda:str(uuid.uuid4()))
    scenario=Column(String(1),nullable=False)
    created_at=Column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    payload=Column(Text,nullable=False)

class Setting(Base):
    __tablename__='nightshift_settings'
    key=Column(String(80),primary_key=True)
    value=Column(Text,nullable=False)

class ChatRequest(Base):
    __tablename__='pliz_chat_requests'
    id=Column(String(40),primary_key=True)
    fingerprint=Column(String(64),nullable=False)
    prompt=Column(Text,nullable=False)
    scenario=Column(String(1),nullable=False)
    status=Column(String(20),nullable=False,default='running')
    payload=Column(Text,nullable=False,default='{}')
    generations=Column(Text,nullable=False,default='[]')
    created_at=Column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

DEMO_NAMES=['Aisha Rahman','Daniel Tan','Priya Nair','Marcus Lim','Nur Aisyah','Ethan Koh',
 'Mei Lin Chen','Arjun Kumar','Siti Aminah','Ryan Wong','Farah Aziz','Wei Jie Ng',
 'Kavitha Devi','Adam Lee','Hana Ibrahim','Lucas Goh','Nadia Hassan','Darren Chua',
 'Rachel Teo','Ravi Menon','Sarah Yeo','Hakim Abdullah','Chloe Ong','Vikram Das']

def initialise():
    Base.metadata.create_all(engine)
    with Session.begin() as session:
        if not session.get(Setting,'seeded'):
            for i,name in enumerate(DEMO_NAMES):
                session.add(Person(name=name,role='Engineer' if i%2==0 else 'Technician',
                  skills='track;construction;consist;electrical' if i%3==0 else 'track;construction;consist',
                  max_shifts=3,demo=True))
            session.add(Setting(key='seeded',value='1'))

def people():
    with Session() as session:
        return [{c:getattr(p,c) for c in ['id','name','role','skills','max_shifts','unavailable','demo','active']}
                for p in session.scalars(select(Person).order_by(Person.name)).all()]

def get_setting(key):
    with Session() as session:
        result=session.get(Setting,key)
        return json.loads(result.value) if result else None

def set_setting(key,value):
    with Session.begin() as session:
        row=session.get(Setting,key)
        if row: row.value=json.dumps(value)
        else: session.add(Setting(key=key,value=json.dumps(value)))
