from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Table, Column, Integer, String, Enum, MetaData, ForeignKey, Unicode, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy.databases import mysql
import datetime
from allchat import app


Base = declarative_base()

class UserInfo(Base):
    __tablename__ = "userinfo"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8'
    }
    
    id = Column(Integer, primary_key = True)
    username = Column(String(50), index = True, unique = True, nullable = False)
    nickname = Column(Unicode(50))
    password = Column(String(50), nullable = False)
    state = Column(Enum(('online', 'invisible', 'offline')), nullable = False)
    method = Column(Enum(('web', 'mobile', 'desktop')))
    getunreadmsg = Column(Boolean, nullable = False, default = False)
    login = Column(DateTime(timezone = True))
    created = Column(DateTime(timezone = True), nullable = False)
    updated = Column(DateTime(timezone = True), nullable = False)
    deleted = Column(Boolean, nullable = False, default = False)
    ip = Column(String(15), nullable = False, default = "0.0.0.0")
    port = Column(Integer, nullable = False, default = 0)
    
    groups = relationship('GroupList', backref=backref('users', order_by=id))
    friends = relationship('FriendList', backref=backref('users', order_by=id))
    
    def __init__(self, username, password, nickname = None, state = None, method = None, 
                getunreadmsg = False, login = None, created = None, updated = None, deleted = False, 
                ip = None, port = None):
        self.username = username
        self.nickname = nickname
        self.password = password
        if state is None:
            self.state = 'offline'
        else:
            self.state = state
        self.method = method
        self.getunreadmsg = getunreadmsg
        self.login = login
        self.created = datetime.datetime.utcnow() if not created else created
        self.updated = self.created if not updated else updated
        self.deleted = deleted
        self.ip = "0.0.0.0" if not ip else ip
        self.port = app.config["CLIENT_PORT"] if not port else port
            
class GroupList(Base):
    __tablename__ = "grouplist"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8'
    }
    id = Column(Integer, primary_key = True)
    group_id = Column(Integer, nullable = False, index = True)
    group_name = Column(Unicode(50))
    role = Column(Enum(('owner', 'manager', 'member')), nullable = False)
    index = Column(Integer, ForeignKey('userinfo.id'))
    
    def __init__(self, group_id,  index, group_name = None, role = "member"):
        self.group_id = group_id
        self.group_name = group_name
        self.role = role
        self.index = index
        
        
class FriendList(Base):
    __tablename__ = "friendlist"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8'
    }
    id = Column(Integer, primary_key = True)
    username = Column(String(50), index = True, unique = True, nullable = False)
    index = Column(Integer, ForeignKey('userinfo.id'))
    
    def __init__(self, username, index):
        self.username = username
        self.index = index

class GroupInfo(Base):
    __tablename__ = "groupinfo"
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8'
    }
    id = Column(Integer, primary_key = True)
    group_id = Column(Integer, nullable = False, index = True, unique = True)
    group_name = Column(Unicode(50))
    owner = Column(String(50), nullable = False)
    created = Column(DateTime(timezone = True), nullable = False)
    updated = Column(DateTime(timezone = True), nullable = False)
    deleted = Column(Boolean, nullable = False, default = False)
    
    def __init__(self, group_id, owner, group_name = None, created = None, updated = None, deleted = False):
        self.group_id = group_id
        self.owner = owner
        self.group_name = group_name
        self.created = datetime.datetime.utcnow() if not created else created
        self.updated = self.created if not updated else updated
        self.deleted = deleted
