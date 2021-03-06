from flask.views import MethodView
from flask import request, make_response, g, session, jsonify
from allchat.database.sql import get_session
from allchat.database.models import UserInfo, GroupMember, FriendList, GroupInfo
from sqlalchemy import and_, desc
from allchat.amqp.Impl_kombu import RPC, cast


class groups_view(MethodView):
    def get(self):
        header = request.headers
        if 'group_id' in header and 'account' in header:
            group_id = header['group_id']
            account = header['account']
            db_session = get_session()
            try:
                db_user = db_session.query(UserInfo).filter_by(username = account).one()
            except:
                return ("Invalid user.", 404)
            # return all the groups the user has joined, including group_id and group_name
            if group_id == str(0):
                try:
                    groups = db_session.query(GroupMember).filter_by(member_account = account).all()
                except:
                    return ("DataBase Failed querying groups info", 503 )
                group_list = dict()
                for group in groups:
                    group_list[group.group_id] = group.group_name
                return (jsonify(group_list), 201)
            # return the member information of the specified group, check if the user is member or not
            else:
                try:
                    group = db_session.query(GroupInfo).join(GroupMember).filter(GroupInfo.group_id == group_id).one()
                except:
                    return ("Group "+group_id+" not found.", 404)
                if account not in [member.member_account for member in group.groupmembers]:
                    return ("You are not in this group, access denied.", 405)
                member_list = dict()
                for member in group.groupmembers:
                    member_info = [ member.member_logstate, member.role]
                    member_list[member.member_account] = member_info
                return (jsonify(member_list), 201)
        else:
            return ("Missing critical information.", 403)
    def post(self):
        if (request.environ['CONTENT_TYPE'].split(';', 1)[0] == "application/json"):
            try:
                para = request.get_json()
            except Exception as e:
                resp = make_response(("The json data can't be parsed", 403, ))
                return resp
            # parse the json data and handle the request
            account = para['account']
            group_name = para['group_name']
            userlist = []
            if 'userlist' in para:
                userlist = para['userlist']
            # allocate group id auto increment by 1, start from 10000
            db_session = get_session()
            try:
                db_user = db_session.query(UserInfo).filter_by(username = account).one()
            except Exception, e:
                return ("User not found", 404)
            max_group_id = db_session.query(GroupInfo.group_id).order_by(desc(GroupInfo.group_id)).first()
            if max_group_id is None:
                group_id = 10000
            else:
                group_id = max_group_id[0]+1
            # add users in userlist to group if userlist is not empty
            # update both GroupMember and GroupInfo 
            members = []
            member = GroupMember(group_id, group_name, account, db_user.state, "owner")
            members.append(member)
            illegal_users = set()
            if userlist:
                for user in {}.fromkeys(userlist).keys(): # eliminate the duplicated account
                    try:
                        db_user = db_session.query(UserInfo).filter_by(username = user).one()
                    except Exception, e:
                        illegal_users.add(user)
                    else:
                        if user != account:
                            member = GroupMember(group_id, group_name, user, db_user.state)
                            members.append(member)
            group = GroupInfo(group_id, account, group_name,len(members))
            db_session.begin()
            for member in members:
                group.groupmembers.append(member)
            db_session.add(group)
            try:
                db_session.commit()
            except:
                db_session.rollback()
                return ("DataBase Failed", 503, )
            if illegal_users:
                return ("Group created,but these users are illegal:"+','.join(illegal_users), 202)
            else:
                return ("Group created successfully!", 201)
        else:
            return ("Please upload a json data", 403)

    def put(self,groupID):
        if groupID is None:
            return ("Error in the URL. Please contain proper group id in the URL.", 403)
        if (request.environ['CONTENT_TYPE'].split(';', 1)[0] == "application/json"):
            # check the account and operation, whether match or not
            # if match then proceed, if not return wrong information
            try:
                para = request.get_json()
            except Exception as e:
                resp = make_response(("The json data can't be parsed", 403, ))
                return resp
            account = para['account']
            operation = para['operation']
            db_session = get_session()
            try:
                db_group = db_session.query(GroupInfo).filter_by(group_id = groupID).one()
            except Exception, e:
                return ("Group not found", 404)
            # this is the group owner try to add or del group member
            if account == db_group.owner:
                if operation not in ["add","del"]:
                    return ("Operation not supported", 405)
                else:
                    if 'userlist' not in para:
                        return ("Userlist missing", 404)
                    # eliminate duplication and validate each user's identity
                    userlist = {}.fromkeys(para["userlist"]).keys()
                    if not userlist:
                        return ("Userlist is empty", 405)
                    existed_members = [member.member_account for member in db_group.groupmembers]
                    # the operation is add, make sure the user is registered and new to the group
                    if operation == "add":
                        new_members = []
                        old_members = []
                        for user in userlist:
                            if user not in existed_members:
                                try:
                                    db_user = db_session.query(UserInfo).filter_by(username = user).one()
                                except Exception, e:
                                    return ("The user "+user+" is not registered yet.", 404)
                                new_members.append(GroupMember(groupID, db_group.group_name, user, db_user.state))
                            else:
                                old_members.append(user)
                        # for users passed validation, add to GroupMember and update group size in GroupInfo
                        if new_members:
                            db_session.begin()
                            for member in new_members:
                                db_group.groupmembers.append(member)
                            db_group.group_size += len(new_members)
                            try:
                                db_session.commit()
                            except:
                                db_session.rollback()
                                return ("DataBase Failed", 503, )
                        if old_members:
                            return ("The following users are already in the group:"+','.join(old_members), 202)
                        else:
                            return ("Users added to the group successfully.", 201)
                    # the operation is del, make sure the user is registered and already in the group
                    if operation == "del":
                        user_req_del = []
                        member_to_del = []
                        non_member = []
                        for user in userlist:
                            if user in existed_members:
                                if user == db_group.owner:
                                    return ("The group owner can't be deleted.", 405)
                                user_req_del.append(user)
                            else:
                                non_member.append(user)
                        # for users passed validation, del from GroupMember and update group size in GroupInfo
                        if user_req_del:
                            for member in db_group.groupmembers:
                                if member.member_account in user_req_del:
                                    member_to_del.append(member)
                            db_session.begin()
                            for member in member_to_del:
                                db_group.groupmembers.remove(member)
                            db_group.group_size -= len(member_to_del)
                            try:
                                db_session.commit()
                            except:
                                db_session.rollback()
                                return ("DataBase Failed", 503, )
                        if non_member:
                            return ("The following users are not group members:"+" ,".join(non_member), 202)
                        else:
                            return ("Users deleted from the group successfully", 201)                        

            # this is a member trying to quit or a non-member trying to join in
            else:
                if operation not in ["join","quit"]:
                    return ("Operation not supported", 405)
                else:
                    if operation == "join":
                        #validate user identity and proceed depend on the result
                        # send group owner an applying msg, when the owner confirms, send the applicant a msg
                        '''
                        // handle procedure of applying msg lies here
                        '''
                        return ("Application has been dealt, please wait for the owner to handle.", 201)
                    if operation == "quit":
                        #validate user identity and proceed depend on the result
                        existed_members = [member.member_account for member in db_group.groupmembers]
                        if account in existed_members:
                            applicant = ''
                            for member in db_group.groupmembers:
                                if member.member_account == account:
                                    applicant = member
                                    break
                            db_session.begin()
                            db_group.groupmembers.remove(applicant)
                            db_group.group_size -= 1
                            try:
                                db_session.commit()
                            except:
                                db_session.rollback()
                                return ("DataBase Failed", 503, )
                            return ("Quit the group successfully.", 201)
                        else:
                            return ("You are not a member of this group.", 405)
        else:
            return ("Please upload a json data", 403)

    def delete(self, groupID):
        if groupID is None:
            return ("Error in the URL. Please contain proper group id in the URL.", 403)
        if (request.environ['CONTENT_TYPE'].split(';', 1)[0] == "application/json"):
            # check whether the applying user is the owner of the group
            try:
                para = request.get_json()
            except Exception as e:
                resp = make_response(("The json data can't be parsed", 403, ))
                return resp
            account = para['account']
            db_session = get_session()
            try:
                db_group = db_session.query(GroupInfo).filter_by(group_id = groupID).one()
            except Exception, e:
                return ("Group not found", 404)
            if account != db_group.owner:
                return ("You don't have the permission to the operation", 405)
            # permission validated, delete the group info from GroupInfo and GroupMember
            db_session.begin()
            db_session.delete(db_group)
            try:
                db_session.commit()
            except:
                db_session.rollback()
                return ("DataBase Failed", 503, )
            return ("Group deleted successfully", 201)
        else:
            return ("Please upload a json data", 403)
