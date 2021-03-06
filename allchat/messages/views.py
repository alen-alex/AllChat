# -*- coding: utf-8 -*-
from flask.views import MethodView
from flask import request, make_response
from flask import jsonify
from allchat.database.sql import get_session
from allchat.database.models import UserInfo, FriendList, GroupInfo, GroupMember
from allchat.amqp.Impl_kombu import send_message, receive_message
from sqlalchemy import and_, or_
import datetime


class messages_view(MethodView):
    def get(self):
        try:
            account = request.headers['account']#这里还需要把这个account和cookie中存的account进行对比
        except Exception,e:
            return ("Can't determine account", 400)
        db_session = get_session()
        try:
            user = db_session.query(UserInfo).filter(and_(UserInfo.deleted == False,
                            UserInfo.state != 'offline', UserInfo.username == account)).one()
        except Exception,e:
            return ("Account {0} doesn't exist".format(account), 404)
        msg = receive_message(user.username)
        if msg:
            return jsonify(msg)
        else:
            return ("Time out", 404)
    def post(self, type):
        content_type = request.environ['CONTENT_TYPE'].split(';', 1)[0]
        tmp = content_type.split(';', 1)[0]
        if tmp == "application/json":
            try:
                if type == "individual":
                    return self.individual_message()
                elif type == "group":
                    return self.individual_message()
                else:
                    return ("Error URL", 403)
            except Exception,e:
                return ("Failed to pass the message", 500)
        else:
            return ("Error Content_Type in the request, please upload a "
                    "application/json request", 403)

    def individual_message(self):
        try:
            para = request.get_json()
        except Exception as e:
            return ("The json data can't be parsed", 403, )
        try:
            sender = request.headers['message_sender']
            receiver = request.headers['message_receiver']
        except Exception,e:
            return ("HTTP header format error", 403)
        db_session = get_session()
        users = db_session.query(UserInfo).join(FriendList).filter(or_(UserInfo.username == sender,
                                UserInfo.username == receiver)).filter(and_(UserInfo.state != "offline",
                                UserInfo.deleted == False)).all()
        if len(users) != 2:
            return ('Message send failed due to account not exist or offline', 403)
        user_from = None
        user_to = None
        flag = False
        if users[0].username == sender:
            user_from = users[0]
            user_to = users[1]
        else:
            user_from = users[1]
            user_to = users[0]
        for friend in user_from.friends:
            if friend.username == user_to.username and friend.confirmed == True:
                flag = True
                break;
        if not flag:
            return ('Forbidden! The recipient is not your friend.', 403)

        message = dict()
        message['method'] = "send_individual_message"
        tmp = dict()
        tmp['from'] = user_from.username
        tmp['to'] = user_to.username
        tmp['time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tmp['msg'] = para['msg']
        message['para'] = tmp
        ret = None
        for i in range(0,3):
            ret = send_message(user_from.username, user_to.username, message)
            if not ret:
                return ("Send message successfully", 200)
            else:
                continue
        return ret


    def group_message(self):
        try:
            para = request.get_json()
        except Exception as e:
            return ("The json data can't be parsed", 403, )
        sender = request.headers['message_sender']
        group_id = request.headers['group_id']
        db_session = get_session()
        try:
            user_from = db_session.query(UserInfo).filter(UserInfo.username == sender).\
                                filter(and_(UserInfo.state != "offline",
                                UserInfo.deleted == False)).one()
        except Exception,e:
            return ('Message send failed due to the sender not exist or offline', 403)
        try:
            group_to = db_session.query(GroupInfo).join(GroupMember).filter(
                                    GroupInfo.id == group_id).one()
        except Exception,e:
            return ("Group doesn't exist", 403)
        message = dict()
        message['method'] = 'send_group_message'
        tmp = dict()
        tmp['from'] = user_from.username
        tmp['to'] = None
        tmp['group_id'] = group_id
        tmp['time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message['para'] = tmp
        failed = []
        for user in group_to.groupmembers:
            if user.member_account == user_from.username:
                continue
            message['para']['to'] = user.member_account
            ret = send_message(user_from.username, user.member_account, message)
            if ret:
                failed.append(user.member_account)
        last = []
        for user in failed:
            ret = None
            for i in range(0, 2):
                message['para']['to'] = user
                ret = send_message(user_from.username, user, message)
                if not ret:
                    break
            if ret:
                last.append(user)
        if len(last) != 0:
            return ('Message send partly failed', 206)
        return ("Send message successfully", 200)



