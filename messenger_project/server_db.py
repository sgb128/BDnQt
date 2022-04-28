from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime


class ServerStorage:
    ServerDB = declarative_base()

    class AllUsers(ServerDB):
        __tablename__ = 'all_users'
        id = Column(Integer, primary_key=True)
        name = Column(String, unique=True)
        last_login = Column(DateTime)

        # ch_rel_a = relationship("ActiveUsers", back_populates="p_rel_a")
        # ch_rel_l = relationship("LoginHistory", back_populates="p_rel_l")

        def __init__(self, name):
            self.name = name
            self.last_login = datetime.now()

        def __repr__(self):
            return f"<AllUsers({self.name},{self.last_login})>"

    class ActiveUsers(ServerDB):
        __tablename__ = 'active_users'
        id = Column(Integer, primary_key=True)
        user = Column(String, ForeignKey('all_users.id'), unique=True)
        ip_address = Column(String)
        port = Column(Integer)
        login_time = Column(DateTime)

        # p_rel_a = relationship("AllUsers", back_populates="ch_rel_a")

        def __init__(self, user, ip_address, port, login_time):
            self.user = user
            self.ip_address = ip_address
            self.port = port
            self.login_time = login_time

        def __repr__(self):
            return f"<ActiveUsers({self.user_id},{self.ip_address},{self.port},{self.login_time})>"

    class LoginHistory(ServerDB):
        __tablename__ = 'login_history'
        id = Column(Integer, primary_key=True)
        user = Column(String, ForeignKey('all_users.id'))
        ip_address = Column(String)
        port = Column(Integer)
        date_login = Column(DateTime)

        # p_rel_l = relationship("AllUsers", back_populates="ch_rel_l")

        def __init__(self, user, ip_address, port, date_login):
            self.user = user
            self.ip_address = ip_address
            self.port = port
            self.date_login = date_login

        def __repr__(self):
            return f"<LoginHistory({self.user_id},{self.ip_address},{self.port},{self.date_login})>"

    class UsersContacts(ServerDB):
        __tablename__ = 'users_contacts'
        id = Column(Integer, primary_key=True)
        user = Column(String, ForeignKey('all_users.id'))
        contact = Column(String, ForeignKey('all_users.id'))

        def __init__(self, user, contact):
            self.id = None
            self.user = user
            self.contact = contact

    class UsersHistory(ServerDB):
        __tablename__ = 'users_history'
        id = Column(Integer, primary_key=True)
        user = Column(String, ForeignKey('all_users.id'))
        sent = Column(Integer)
        receive = Column(Integer)

        def __init__(self, user, sent, receive):
            self.id = None
            self.user = user
            self.sent = sent
            self.receive = receive

    def __init__(self, path):
        self.engine = create_engine(f'sqlite:///{path}', echo=False, pool_recycle=7200,
                                    connect_args={'check_same_thread': False})
        self.ServerDB.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.session.query(self.ActiveUsers).delete()
        self.session.commit()

    def user_login(self, username, ip_address, port):
        curs = self.session.query(self.AllUsers).filter_by(name=username)
        if curs.count():
            user = curs.first()
            user.last_login = datetime.now()
        else:
            user = self.AllUsers(username)
            self.session.add(user)
            self.session.commit()
            user_in_history = self.UsersHistory(user.id)
            self.session.add(user_in_history)
        new_active_user = self.ActiveUsers(user.id, ip_address, port, datetime.now())
        self.session.add(new_active_user)
        history = self.LoginHistory(user.id, ip_address, port, datetime.now())
        self.session.add(history)
        self.session.commit()

    def user_logout(self, username):
        user = self.session.query(self.AllUsers).filter_by(name=username).first()
        self.session.query(self.ActiveUsers).filter_by(name=user.id).delete()
        self.session.commit()

    def users_list(self):
        query = self.session.query(
            self.AllUsers.name,
            self.AllUsers.last_login
        )
        return query.all()

    def active_users_list(self):
        query = self.session.query(
            self.AllUsers.name,
            self.ActiveUsers.ip_address,
            self.ActiveUsers.port,
            self.ActiveUsers.login_time
        ).join(self.AllUsers)
        return query.all()

    def login_history(self, username=None):
        query = self.session.query(
            self.AllUsers.name,
            self.LoginHistory.date_login,
            self.LoginHistory.ip_address,
            self.LoginHistory.port
        ).join(self.AllUsers)
        if username:
            query = query.filter(self.AllUsers.name == username)
        return query.all()

    def process_message(self, sender, recipient):
        sender = self.session.query(self.AllUsers).filter_by(name=sender).first().id
        recipient = self.session.query(self.AllUsers).filter_by(name=recipient).first().id
        sender_row = self.session.query(self.UsersHistory).filter_by(user=sender).first()
        sender_row.sent += 1
        recipient_row = self.session.query(self.UsersHistory).filter_by(user=recipient).first()
        recipient_row.accepted += 1
        self.session.commit()

    def add_contact(self, user, contact):
        user = self.session.query(self.AllUsers).filter_by(name=user).first()
        contact = self.session.query(self.AllUsers).filter_by(name=contact).first()
        if not contact or self.session.query(self.UsersContacts).filter_by(user=user.id, contact=contact.id).count():
            return
        contact_row = self.UsersContacts(user.id, contact.id)
        self.session.add(contact_row)
        self.session.commit()

    def remove_contact(self, user, contact):
        user = self.session.query(self.AllUsers).filter_by(name=user).first()
        contact = self.session.query(self.AllUsers).filter_by(name=contact).first()
        if not contact:
            return
        self.session.query(self.UsersContacts).filter(
            self.UsersContacts.user == user.id,
            self.UsersContacts.contact == contact.id
        ).delete()
        self.session.commit()

    def get_contacts(self, username):
        user = self.session.query(self.AllUsers).filter_by(name=username).one()
        query = self.session.query(self.UsersContacts, self.AllUsers.name). \
            filter_by(user=user.id). \
            join(self.AllUsers, self.UsersContacts.contact == self.AllUsers.id)
        return [contact[1] for contact in query.all()]

    def message_history(self):
        query = self.session.query(
            self.AllUsers.name,
            self.AllUsers.last_login,
            self.UsersHistory.sent,
            self.UsersHistory.accepted
        ).join(self.AllUsers)
        return query.all()


if __name__ == '__main__':
    test_db = ServerStorage()
    # Подключение пользователей
    test_db.user_login('sgb1', '192.168.0.1', 8888)
    test_db.user_login('sgb2', '192.168.0.2', 8889)
    # Список активных пользователей
    print('Список активных пользователей')
    print(test_db.active_users_list())
    # Список истории входов пользователя sgb1
    print('Список истории входов пользователя sgb1')
    print(test_db.login_history('sgb1'))

# Комментарий только для 3го урока. Я потратил кучу времени прежде чем понял в чем проблема.
# Настоятельно рекомендую использовать обычный(не встроенный) менеджер БД потому, что тот менеджер, который посоветовали
# как плагин для PyCharm нужно еще донастраивать(если это вообще возможно) таким образом, чтобы он отображал столбцы
# по которым происходит связь с родительской таблицей. У меня эти столбцы не отображжались и я понять не мог почему они
# не создаются... Вот так вот пользоваться непроверенными средствами разработки.
