from sqlalchemy import create_engine, Table, Column, Integer, String, Text, MetaData, DateTime, ForeignKey
from sqlalchemy.orm import mapper, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from common.variables import *
import datetime


class ClientDatabase:
    ClientDB = declarative_base()

    class KnownUsers(ClientDB):
        __tablename__ = 'known_users'
        id = Column(Integer, primary_key=True)
        username = Column(String)

        def __init__(self, user):
            self.id = None
            self.username = user

    class MessageHistory(ClientDB):
        __tablename__ = 'message_history'
        id = Column(Integer, primary_key=True)
        from_user = Column(String, ForeignKey('known_users.id'))
        to_user = Column(String, ForeignKey('known_users.id'))
        message = Column(Text)
        date = Column(DateTime)

        def __init__(self, from_user, to_user, message):
            self.id = None
            self.from_user = from_user
            self.to_user = to_user
            self.message = message
            self.date = datetime.datetime.now()

    class Contacts(ClientDB):
        __tablename__ = 'contacts'
        id = Column(Integer, primary_key=True)
        name = Column(String, ForeignKey('known_users.id'), unique=True)

        def __init__(self, contact):
            self.id = None
            self.name = contact

    def __init__(self, name):
        self.database_engine = create_engine(f'sqlite:///client_{name}.db3',
                                             echo=False,
                                             pool_recycle=7200,
                                             connect_args={'check_same_thread': False})

        self.ClientDB.metadata.create_all(self.engine)
        self.metadata.create_all(self.database_engine)

        Session = sessionmaker(bind=self.database_engine)
        self.session = Session()
        self.session.query(self.Contacts).delete()
        self.session.commit()

    def add_contact(self, contact):
        if not self.session.query(self.Contacts).filter_by(name=contact).count():
            contact_row = self.Contacts(contact)
            self.session.add(contact_row)
            self.session.commit()

    def del_contact(self, contact):
        self.session.query(self.Contacts).filter_by(name=contact).delete()
        self.session.commit()

    def add_users(self, users_list):
        self.session.query(self.KnownUsers).delete()
        for user in users_list:
            user_row = self.KnownUsers(user)
            self.session.add(user_row)
        self.session.commit()

    def save_message(self, from_user, to_user, message):
        message_row = self.MessageHistory(from_user, to_user, message)
        self.session.add(message_row)
        self.session.commit()

    def get_contacts(self):
        return [contact[0] for contact in self.session.query(self.Contacts.name).all()]

    def get_users(self):
        return [user[0] for user in self.session.query(self.KnownUsers.username).all()]

    def check_user(self, user):
        if self.session.query(self.KnownUsers).filter_by(username=user).count():
            return True
        else:
            return False

    def check_contact(self, contact):
        if self.session.query(self.Contacts).filter_by(name=contact).count():
            return True
        else:
            return False

    def get_history(self, from_who=None, to_who=None):
        query = self.session.query(self.MessageHistory)
        if from_who:
            query = query.filter_by(from_user=from_who)
        if to_who:
            query = query.filter_by(to_user=to_who)
        return [(history_row.from_user, history_row.to_user, history_row.message, history_row.date)
                for history_row in query.all()]


if __name__ == '__main__':
    test_db = ClientDatabase('sgb1')
    for i in ['sgb3', 'sgb4', 'sgb5']:
        test_db.add_contact(i)
    test_db.add_contact('sgb4')
    test_db.add_users(['sgb1', 'sgb2', 'sgb3', 'sgb4', 'sgb5'])
    test_db.save_message('sgb1', 'sgb2',
                         f'Привет! я тестовое сообщение от {datetime.datetime.now()}!')
    test_db.save_message('sgb2', 'sgb1',
                         f'Привет! я другое тестовое сообщение от {datetime.datetime.now()}!')
    print(test_db.get_contacts())
    print(test_db.get_users())
    print(test_db.check_user('sgb1'))
    print(test_db.check_user('sgb10'))
    print(test_db.get_history('sgb2'))
    print(test_db.get_history(to_who='sgb2'))
    print(test_db.get_history('sgb3'))
    test_db.del_contact('sgb4')
    print(test_db.get_contacts())
