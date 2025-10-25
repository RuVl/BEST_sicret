from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Category(Base):
    __tablename__ = 'category'
    id = Column(Integer, primary_key=True)
    name = Column(String)

class Place(Base):
    __tablename__ = 'place'
    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey('person.id'))
    address = Column(String)

class Person(Base):
    __tablename__ = 'person'
    id = Column(Integer, primary_key=True)

class Item(Base):
    __tablename__ = 'item'
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('category.id'))
    name = Column(String)
    count = Column(Integer)
    unit = Column(String)
    place_id = Column(Integer, ForeignKey('place.id'))



from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Category(Base):
    __tablename__ = 'category'
    id = Column(Integer, primary_key=True)
    name = Column(String)

class Item(Base):
    __tablename__ = 'item'
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('category.id'))
    name = Column(String)
    count = Column(Integer)
    unit = Column(String)