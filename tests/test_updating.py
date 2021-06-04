# test_updating.py - unit tests for updating resources
#
# Copyright 2011 Lincoln de Sousa <lincoln@comum.org>.
# Copyright 2012, 2013, 2014, 2015, 2016 Jeffrey Finkelstein
#           <jeffrey.finkelstein@gmail.com> and contributors.
#
# This file is part of Flask-Restless.
#
# Flask-Restless is distributed under both the GNU Affero General Public
# License version 3 and under the 3-clause BSD license. For more
# information, see LICENSE.AGPL and LICENSE.BSD.
"""Unit tests for updating resources from endpoints generated by
Flask-Restless.

This module includes tests for additional functionality that is not
already tested by :mod:`test_jsonapi`, the package that guarantees
Flask-Restless meets the minimum requirements of the JSON API
specification.

"""
from __future__ import division

from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Time
from sqlalchemy import Unicode
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import backref
from sqlalchemy.orm import relationship

from flask_restless import CONTENT_TYPE
from flask_restless import APIManager
from flask_restless import ProcessingException

from .helpers import BetterJSONEncoder as JSONEncoder
from .helpers import FlaskSQLAlchemyTestBase
from .helpers import ManagerTestBase
from .helpers import check_sole_error
from .helpers import dumps
from .helpers import loads

try:
    from flask_sqlalchemy import SQLAlchemy
except ImportError:
    has_flask_sqlalchemy = False
else:
    has_flask_sqlalchemy = True


class TestUpdating(ManagerTestBase):
    """Tests for updating resources."""

    def setUp(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask_restless.manager.APIManager` for that application, and
        creates the ReSTful API endpoints for the :class:`TestSupport.Person`
        and :class:`TestSupport.Article` models.

        """
        super(TestUpdating, self).setUp()

        class Article(self.Base):
            __tablename__ = 'article'
            id = Column(Integer, primary_key=True)
            author = relationship('Person', backref=backref('articles'))
            author_id = Column(Integer, ForeignKey('person.id'))

        class Person(self.Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)
            name = Column(Unicode, unique=True)
            bedtime = Column(Time)
            date_created = Column(Date)
            birth_datetime = Column(DateTime)

        # This example comes from the SQLAlchemy documentation.
        #
        # The SQLAlchemy documentation is licensed under the MIT license.
        class Interval(self.Base):
            __tablename__ = 'interval'
            id = Column(Integer, primary_key=True)
            start = Column(Integer, nullable=False)
            end = Column(Integer, nullable=False)

            @hybrid_property
            def length(self):
                return self.end - self.start

            @length.setter
            def length(self, value):
                self.end = self.start + value

            @hybrid_property
            def radius(self):
                return self.length / 2

            @radius.expression
            def radius(cls):
                return cls.length / 2

        self.Article = Article
        self.Interval = Interval
        self.Person = Person
        self.Base.metadata.create_all()
        self.manager.create_api(Article, methods=['PATCH'])
        self.manager.create_api(Interval, methods=['PATCH'])
        self.manager.create_api(Person, methods=['PATCH'])

    def test_wrong_content_type(self):
        """Tests that if a client specifies only :http:header:`Accept`
        headers with non-JSON API media types, then the server responds
        with a :http:status:`415`.

        """
        person = self.Person(id=1, name=u'foo')
        self.session.add(person)
        self.session.commit()
        headers = {'Content-Type': 'application/json'}
        data = {
            'data': {
                'type': 'person',
                'id': 1,
                'attributes': {
                    'name': 'bar'
                }
            }
        }
        response = self.app.patch('/api/person/1', data=dumps(data),
                                  headers=headers)
        assert response.status_code == 415
        assert person.name == u'foo'

    def test_wrong_accept_header(self):
        """Tests that if a client specifies only :http:header:`Accept`
        headers with non-JSON API media types, then the server responds
        with a :http:status:`406`.

        """
        person = self.Person(id=1, name=u'foo')
        self.session.add(person)
        self.session.commit()
        headers = {'Accept': 'application/json'}
        data = {
            'data': {
                'type': 'person',
                'id': 1,
                'attributes': {
                    'name': 'bar'
                }
            }
        }
        response = self.app.patch('/api/person/1', data=dumps(data),
                                  headers=headers)
        assert response.status_code == 406
        assert person.name == u'foo'

    def test_related_resource_url_forbidden(self):
        """Tests that :http:method:`patch` requests to a related resource URL
        are forbidden.

        """
        article = self.Article(id=1)
        person = self.Person(id=1)
        self.session.add_all([article, person])
        self.session.commit()
        data = dict(data=dict(type='person', id=1))
        response = self.app.patch('/api/article/1/author', data=dumps(data))
        assert response.status_code == 405
        # TODO check error message here
        assert article.author is None

    def test_deserializing_time(self):
        """Test for deserializing a JSON representation of a time field."""
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        bedtime = datetime.now().time()
        data = {
            'data': {
                'type': 'person',
                'id': '1',
                'attributes': {
                    'bedtime': bedtime
                }
            }
        }
        # Python's built-in JSON encoder doesn't serialize date/time objects by
        # default.
        data = dumps(data, cls=JSONEncoder)
        response = self.app.patch('/api/person/1', data=data)
        assert response.status_code == 204
        assert person.bedtime == bedtime

    def test_deserializing_date(self):
        """Test for deserializing a JSON representation of a date field."""
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        today = datetime.now().date()
        data = {
            'data': {
                'type': 'person',
                'id': '1',
                'attributes': {
                    'date_created': today
                }
            }
        }
        # Python's built-in JSON encoder doesn't serialize date/time objects by
        # default.
        data = dumps(data, cls=JSONEncoder)
        response = self.app.patch('/api/person/1', data=data)
        assert response.status_code == 204
        assert person.date_created == today

    def test_deserializing_datetime(self):
        """Test for deserializing a JSON representation of a date field."""
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        now = datetime.now()
        data = {
            'data': {
                'type': 'person',
                'id': '1',
                'attributes': {
                    'birth_datetime': now
                }
            }
        }
        # Python's built-in JSON encoder doesn't serialize date/time objects by
        # default.
        data = dumps(data, cls=JSONEncoder)
        response = self.app.patch('/api/person/1', data=data)
        assert response.status_code == 204
        assert person.birth_datetime == now

    def test_correct_content_type(self):
        """Tests that the server responds with :http:status:`201` if the
        request has the correct JSON API content type.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        data = dict(data=dict(type='person', id='1'))
        response = self.app.patch('/api/person/1', data=dumps(data),
                                  content_type=CONTENT_TYPE)
        assert response.status_code == 204
        assert response.headers['Content-Type'] == CONTENT_TYPE

    def test_no_content_type(self):
        """Tests that the server responds with :http:status:`415` if the
        request has no content type.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        data = dict(data=dict(type='person', id='1'))
        response = self.app.patch('/api/person/1', data=dumps(data),
                                  content_type=None)
        assert response.status_code == 415
        assert response.headers['Content-Type'] == CONTENT_TYPE

    def test_rollback_on_integrity_error(self):
        """Tests that an integrity error in the database causes a session
        rollback, and that the server can still process requests correctly
        after this rollback.

        """
        person1 = self.Person(id=1, name=u'foo')
        person2 = self.Person(id=2, name=u'bar')
        self.session.add_all([person1, person2])
        self.session.commit()
        data = {
            'data': {
                'type': 'person',
                'id': '2',
                'attributes': {
                    'name': u'foo'
                }
            }
        }
        response = self.app.patch('/api/person/2', data=dumps(data))
        assert response.status_code == 409  # Conflict
        assert self.session.is_active, 'Session is in `partial rollback` state'
        data = {
            'data': {
                'type': 'person',
                'id': '2',
                'attributes': {
                    'name': 'baz'
                }
            }
        }
        response = self.app.patch('/api/person/2', data=dumps(data))
        assert response.status_code == 204
        assert person2.name == 'baz'

    def test_empty_request(self):
        """Test for making a :http:method:`patch` request with no data."""
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        response = self.app.patch('/api/person/1')
        assert response.status_code == 400
        # TODO check the error message here

    def test_empty_string(self):
        """Test for making a :http:method:`patch` request with an empty string,
        which is invalid JSON.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        response = self.app.patch('/api/person/1', data='')
        assert response.status_code == 400
        # TODO check the error message here

    def test_invalid_json(self):
        """Tests that a request with invalid JSON yields an error response."""
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        response = self.app.patch('/api/person/1', data='Invalid JSON string')
        assert response.status_code == 400
        # TODO check error message here

    def test_nonexistent_attribute(self):
        """Tests that attempting to make a :http:method:`patch` request on an
        attribute that does not exist on the specified model yields an error
        response.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        data = {
            'data': {
                'type': 'person',
                'id': '1',
                'attributes': {
                    'bogus': 0
                }
            }
        }
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert 400 == response.status_code

    def test_read_only_hybrid_property(self):
        """Tests that an attempt to set a read-only hybrid property causes an
        error.

        For more information, see issue #171.

        """
        interval = self.Interval(id=1, start=5, end=10)
        self.session.add(interval)
        self.session.commit()
        data = {
            'data': {
                'type': 'interval',
                'id': '1',
                'attributes': {
                    'radius': 1
                }
            }
        }
        response = self.app.patch('/api/interval/1', data=dumps(data))
        assert response.status_code == 400
        # TODO check error message here

    def test_set_hybrid_property(self):
        """Tests that a hybrid property can be correctly set by a client."""
        interval = self.Interval(id=1, start=5, end=10)
        self.session.add(interval)
        self.session.commit()
        data = {
            'data': {
                'type': 'interval',
                'id': '1',
                'attributes': {
                    'length': 4
                }
            }
        }
        response = self.app.patch('/api/interval/1', data=dumps(data))
        assert response.status_code == 204
        assert interval.start == 5
        assert interval.end == 9
        assert interval.radius == 2

    def test_collection_name(self):
        """Tests for updating a resource with an alternate collection name."""
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        self.manager.create_api(self.Person, methods=['PATCH'],
                                collection_name='people')
        data = {
            'data': {
                'type': 'people',
                'id': '1',
                'attributes': {
                    'name': u'foo'
                }
            }
        }
        response = self.app.patch('/api/people/1', data=dumps(data))
        assert response.status_code == 204
        assert person.name == u'foo'

    def test_different_endpoints(self):
        """Tests for updating the same resource from different endpoints."""
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        self.manager.create_api(self.Person, methods=['PATCH'],
                                url_prefix='/api2')
        data = {
            'data': {
                'type': 'person',
                'id': '1',
                'attributes': {
                    'name': u'foo'
                }
            }
        }
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert response.status_code == 204
        assert person.name == u'foo'
        data = {
            'data': {
                'type': 'person',
                'id': '1',
                'attributes': {
                    'name': u'bar'
                }
            }
        }
        response = self.app.patch('/api2/person/1', data=dumps(data))
        assert response.status_code == 204
        assert person.name == 'bar'

    # TODO This is not required by JSON API, and it was a little bit flimsy
    # anyway.
    #
    # def test_patch_update_relations(self):
    #     """Test for posting a new model and simultaneously adding related
    #     instances *and* updating information on those instances.

    #     For more information see issue #164.

    #     """
    #     # First, create a new computer object with an empty `name` field and
    #     # a new person with no related computers.
    #     response = self.app.post('/api/computer', data=dumps({}))
    #     assert 201 == response.status_code
    #     response = self.app.post('/api/person', data=dumps({}))
    #     assert 201 == response.status_code
    #     # Second, patch the person by setting its list of related computer
    #     # instances to include the previously created computer, *and*
    #     # simultaneously update the `name` attribute of that computer.
    #     data = dict(computers=[dict(id=1, name='foo')])
    #     response = self.app.patch('/api/person/1', data=dumps(data))
    #     assert 200 == response.status_code
    #     # Check that the computer now has its `name` field set.
    #     response = self.app.get('/api/computer/1')
    #     assert 200 == response.status_code
    #     assert 'foo' == loads(response.data)['name']
    #     # Add a new computer by patching person
    #     data = {'computers': [{'id': 1},
    #                           {'name': 'iMac', 'vendor': 'Apple',
    #                            'programs': [{'program':{'name':'iPhoto'}}]}]}
    #     response = self.app.patch('/api/person/1', data=dumps(data))
    #     assert 200 == response.status_code
    #     response = self.app.get('/api/computer/2/programs')
    #     programs = loads(response.data)['objects']
    #     assert programs[0]['program']['name'] == 'iPhoto'
    #     # Add a program to the computer through the person
    #     data = {'computers': [{'id': 1},
    #                           {'id': 2,
    #                            'programs': [{'program_id': 1},
    #                                         {'program':{'name':'iMovie'}}]}]}
    #     response = self.app.patch('/api/person/1', data=dumps(data))
    #     assert 200 == response.status_code
    #     response = self.app.get('/api/computer/2/programs')
    #     programs = loads(response.data)['objects']
    #     assert programs[1]['program']['name'] == 'iMovie'

    # TODO this is not required by the JSON API spec.
    #
    # def test_put_same_as_patch(self):
    #     """Tests that :http:method:`put` requests are the same as
    #     :http:method:`patch` requests.

    #     """
    #     # recreate the api to allow patch many at /api/v2/person
    #     self.manager.create_api(self.Person, methods=['GET', 'POST', 'PUT'],
    #                             allow_patch_many=True, url_prefix='/api/v2')

    #     # Creating some people
    #     self.app.post('/api/v2/person',
    #                   data=dumps({'name': u'Lincoln', 'age': 23}))
    #     self.app.post('/api/v2/person',
    #                   data=dumps({'name': u'Lucy', 'age': 23}))
    #     self.app.post('/api/v2/person',
    #                   data=dumps({'name': u'Mary', 'age': 25}))

    #     # change a single entry
    #     resp = self.app.put('/api/v2/person/1', data=dumps({'age': 24}))
    #     assert resp.status_code == 200

    #     resp = self.app.get('/api/v2/person/1')
    #     assert resp.status_code == 200
    #     assert loads(resp.data)['age'] == 24

    #     # Changing the birth date field of the entire collection
    #     day, month, year = 15, 9, 1986
    #     birth_date = date(year, month, day).strftime('%d/%m/%Y')  # iso8601
    #     form = {'birth_date': birth_date}
    #     self.app.put('/api/v2/person', data=dumps(form))

    #     # Finally, testing if the change was made
    #     response = self.app.get('/api/v2/person')
    #     loaded = loads(response.data)['objects']
    #     for i in loaded:
    #         expected = '{0:4d}-{1:02d}-{2:02d}'.format(year, month, day)
    #         assert i['birth_date'] == expected

    # TODO no longer supported
    #
    # def test_patch_autodelete_submodel(self):
    #     """Tests the automatic deletion of entries marked with the
    #     ``__delete__`` flag on an update operation.

    #     It also tests adding an already created instance as a related item.

    #     """
    #     # Creating all rows needed in our test
    #     person_data = {'name': u'Lincoln', 'age': 23}
    #     resp = self.app.post('/api/person', data=dumps(person_data))
    #     assert resp.status_code == 201
    #     comp_data = {'name': u'lixeiro', 'vendor': u'Lemote'}
    #     resp = self.app.post('/api/computer', data=dumps(comp_data))
    #     assert resp.status_code == 201

    #     # updating person to add the computer
    #     update_data = {'computers': {'add': [{'id': 1}]}}
    #     self.app.patch('/api/person/1', data=dumps(update_data))

    #     # Making sure that everything worked properly
    #     resp = self.app.get('/api/person/1')
    #     assert resp.status_code == 200
    #     loaded = loads(resp.data)
    #     assert len(loaded['computers']) == 1
    #     assert loaded['computers'][0]['name'] == u'lixeiro'

    #     # Now, let's remove it and delete it
    #     update2_data = {
    #         'computers': {
    #             'remove': [
    #                 {'id': 1, '__delete__': True},
    #             ],
    #         },
    #     }
    #     resp = self.app.patch('/api/person/1', data=dumps(update2_data))
    #     assert resp.status_code == 200

    #     # Testing to make sure it was removed from the related field
    #     resp = self.app.get('/api/person/1')
    #     assert resp.status_code == 200
    #     loaded = loads(resp.data)
    #     assert len(loaded['computers']) == 0

    #     # Making sure it was removed from the database
    #     resp = self.app.get('/api/computer/1')
    #     assert resp.status_code == 404

    def test_to_one_related_resource_url(self):
        """Tests that attempting to update a to-one related resource URL
        (instead of a relationship URL) yields an error response.

        """
        article = self.Article(id=1)
        person = self.Person(id=1)
        self.session.add_all([article, person])
        self.session.commit()
        data = dict(data=dict(id=1, type='person'))
        response = self.app.patch('/api/article/1/author', data=dumps(data))
        assert response.status_code == 405
        # TODO check error message here

    def test_to_many_related_resource_url(self):
        """Tests that attempting to update a to-many related resource URL
        (instead of a relationship URL) yields an error response.

        """
        article = self.Article(id=1)
        person = self.Person(id=1)
        self.session.add_all([article, person])
        self.session.commit()
        data = dict(data=[dict(id=1, type='article')])
        response = self.app.patch('/api/person/1/articles', data=dumps(data))
        assert response.status_code == 405
        # TODO check error message here

    def test_to_many_null(self):
        """Tests that attempting to set a to-many relationship to null
        yields an error response.

        The JSON API protocol requires that a to-many relationship can
        only be updated (if allowed) with a list.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        self.manager.create_api(self.Person, url_prefix='/api2',
                                methods=['PATCH'],
                                allow_to_many_replacement=True)
        data = {
            'data': {
                'type': 'person',
                'id': '1',
                'relationships': {
                    'articles': {
                        'data': None
                    }
                }
            }
        }
        response = self.app.patch('/api2/person/1', data=dumps(data))
        check_sole_error(response, 400, ['articles', 'data', 'empty list'])

    def test_missing_type(self):
        """Tests that attempting to update a resource without providing a
        resource type yields an error.

        """
        person = self.Person(id=1, name=u'foo')
        self.session.add(person)
        self.session.commit()
        data = {
            'data': {
                'id': '1',
                'attributes': {
                    'name': u'bar'
                }
            }
        }
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert response.status_code == 400
        # TODO check error message here
        assert person.name == u'foo'

    def test_missing_id(self):
        """Tests that attempting to update a resource without providing an ID
        yields an error.

        """
        person = self.Person(id=1, name=u'foo')
        self.session.add(person)
        self.session.commit()
        data = {
            'data': {
                'type': 'person',
                'attributes': {
                    'name': u'bar'
                }
            }
        }
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert response.status_code == 400
        # TODO check error message here
        assert person.name == u'foo'

    def test_nonexistent_to_one_link(self):
        """Tests that an attempt to update a to-one relationship with a
        resource that doesn't exist yields an error.

        """
        article = self.Article(id=1)
        self.session.add(article)
        self.session.commit()
        data = {
            'data': {
                'type': 'article',
                'id': '1',
                'relationships': {
                    'author': {
                        'data': {
                            'type': 'person',
                            'id': '1'
                        }
                    }
                }
            }
        }
        response = self.app.patch('/api/article/1', data=dumps(data))
        check_sole_error(response, 404, ['found', 'person', '1'])

    def test_conflicting_type_to_one_link(self):
        """Tests that an attempt to update a to-one relationship with a linkage
        object whose type does not match the expected resource type yields an
        error.

        """
        person = self.Person(id=1)
        article = self.Article(id=1)
        self.session.add_all([article, person])
        self.session.commit()
        data = {
            'data': {
                'type': 'article',
                'id': '1',
                'relationships': {
                    'author': {
                        'data': {
                            'type': 'bogus',
                            'id': '1'
                        }
                    }
                }
            }
        }
        response = self.app.patch('/api/article/1', data=dumps(data))
        assert response.status_code == 409
        # TODO check error message here

    def test_conflicting_type_to_many_link(self):
        """Tests that an attempt to update a to-many relationship with a
        linkage object whose type does not match the expected resource type
        yields an error.

        """
        person = self.Person(id=1)
        article = self.Article(id=1)
        self.session.add_all([article, person])
        self.session.commit()
        self.manager.create_api(self.Person, methods=['PATCH'],
                                url_prefix='/api2',
                                allow_to_many_replacement=True)
        data = {
            'data': {
                'type': 'person',
                'id': '1',
                'relationships': {
                    'articles': {
                        'data': [
                            {'type': 'bogus', 'id': '1'}
                        ]
                    }
                }
            }
        }
        response = self.app.patch('/api2/person/1', data=dumps(data))
        assert response.status_code == 409
        # TODO check error message here

    def test_relationship_empty_object(self):
        """Tests for an error response on a missing ``'data'`` key in a
        relationship object.

        """
        article = self.Article(id=1)
        self.session.add(article)
        self.session.commit()
        data = {
            'data': {
                'type': 'article',
                'id': '1',
                'relationships': {
                    'author': {}
                }
            }
        }
        response = self.app.patch('/api/article/1', data=dumps(data))
        assert response.status_code == 400
        # TODO check error message here

    def test_relationship_missing_object(self):
        """Tests that a request document missing a relationship object
        causes an error response.

        """
        person = self.Person(id=1)
        article = self.Article(id=1)
        article.author = person
        self.session.add_all([article, person])
        self.session.commit()
        data = {
            'data': {
                'id': '1',
                'type': 'article',
                'relationships': {
                    'author': None
                }
            }
        }
        response = self.app.patch('/api/article/1', data=dumps(data))
        check_sole_error(response, 400, ['missing', 'relationship object',
                                         'author'])
        # Check that the article was not updated to None.
        assert article.author is person


class TestProcessors(ManagerTestBase):
    """Tests for pre- and postprocessors."""

    def setUp(self):
        super(TestProcessors, self).setUp()

        class Person(self.Base):
            __tablename__ = 'person'
            id = Column(Integer, primary_key=True)
            name = Column(Unicode)

        self.Person = Person
        self.Base.metadata.create_all()

    def test_change_id(self):
        """Tests that a return value from a preprocessor overrides the ID of
        the resource to fetch as given in the request URL.

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()

        def increment_id(resource_id=None, **kw):
            if resource_id is None:
                raise ProcessingException
            return str(int(resource_id) + 1)

        preprocessors = dict(PATCH_RESOURCE=[increment_id])
        self.manager.create_api(self.Person, methods=['PATCH'],
                                preprocessors=preprocessors)
        data = {
            'data': {
                'id': '1',
                'type': 'person',
                'attributes': {
                    'name': u'foo'
                }
            }
        }
        response = self.app.patch('/api/person/0', data=dumps(data))
        assert response.status_code == 204
        assert person.name == u'foo'

    def test_single_resource_processing_exception(self):
        """Tests for a preprocessor that raises a :exc:`ProcessingException`
        when updating a single resource.

        """
        person = self.Person(id=1, name=u'foo')
        self.session.add(person)
        self.session.commit()

        def forbidden(**kw):
            raise ProcessingException(status=403, detail='forbidden')

        preprocessors = dict(PATCH_RESOURCE=[forbidden])
        self.manager.create_api(self.Person, methods=['PATCH'],
                                preprocessors=preprocessors)
        data = {
            'data': {
                'id': '1',
                'type': 'person',
                'attributes': {
                    'name': u'bar'
                }
            }
        }
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert response.status_code == 403
        document = loads(response.data)
        errors = document['errors']
        assert len(errors) == 1
        error = errors[0]
        assert 'forbidden' == error['detail']
        assert person.name == u'foo'

    def test_single_resource(self):
        """Tests :http:method:`patch` requests for a single resource with a
        preprocessor function.

        """
        person = self.Person(id=1, name=u'foo')
        self.session.add(person)
        self.session.commit()

        def set_name(data=None, **kw):
            """Sets the name attribute of the incoming data object, regardless
            of the value requested by the client.

            """
            if data is not None:
                data['data']['attributes']['name'] = u'bar'

        preprocessors = dict(PATCH_RESOURCE=[set_name])
        self.manager.create_api(self.Person, methods=['PATCH'],
                                preprocessors=preprocessors)
        data = {
            'data': {
                'id': '1',
                'type': 'person',
                'attributes': {
                    'name': u'baz'
                }
            }
        }
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert response.status_code == 204
        assert person.name == 'bar'

    def test_postprocessor(self):
        """Tests that a request to update a resource invokes a postprocessor.

        """
        person = self.Person(id=1, name=u'foo')
        self.session.add(person)
        self.session.commit()

        temp = []

        def modify_result(result=None, **kw):
            temp.append('baz')

        postprocessors = dict(PATCH_RESOURCE=[modify_result])
        self.manager.create_api(self.Person, methods=['PATCH'],
                                postprocessors=postprocessors)
        data = {
            'data': {
                'id': '1',
                'type': 'person',
                'attributes': {
                    'name': u'bar'
                }
            }
        }
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert response.status_code == 204
        assert person.name == 'bar'
        assert temp == ['baz']


class TestAssociationProxy(ManagerTestBase):
    """Tests for creating an object with a relationship using an association
    proxy.

    """

    def setUp(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask_restless.manager.APIManager` for that application,
        and creates the ReSTful API endpoints for the models used in the test
        methods.

        """
        super(TestAssociationProxy, self).setUp()

        class Article(self.Base):
            __tablename__ = 'article'
            id = Column(Integer, primary_key=True)
            tags = association_proxy('articletags', 'tag',
                                     creator=lambda tag: ArticleTag(tag=tag))

        class ArticleTag(self.Base):
            __tablename__ = 'articletag'
            article_id = Column(Integer, ForeignKey('article.id'),
                                primary_key=True)
            article = relationship(Article, backref=backref('articletags'))
            tag_id = Column(Integer, ForeignKey('tag.id'), primary_key=True)
            tag = relationship('Tag')
            # This is extra information that only appears in this association
            # object.
            extrainfo = Column(Unicode)
            # TODO this dummy column is required to create an API for this
            # object.
            id = Column(Integer)

        class Tag(self.Base):
            __tablename__ = 'tag'
            id = Column(Integer, primary_key=True)
            name = Column(Unicode)

        self.Article = Article
        self.ArticleTag = ArticleTag
        self.Tag = Tag
        self.Base.metadata.create_all()
        self.manager.create_api(Article, methods=['PATCH'])
        # HACK Need to create APIs for these other models because otherwise
        # we're not able to create the link URLs to them.
        #
        # TODO Fix this by simply not creating links to related models for
        # which no API has been made.
        self.manager.create_api(Tag)
        self.manager.create_api(ArticleTag)

    def test_update(self):
        """Test for updating a model with a many-to-many relation that uses an
        association object to allow extra data to be stored in the association
        table.

        For more info, see issue #166.

        """
        article = self.Article(id=1)
        tag1 = self.Tag(id=1)
        tag2 = self.Tag(id=2)
        self.session.add_all([article, tag1, tag2])
        self.session.commit()
        self.manager.create_api(self.Article, methods=['PATCH'],
                                url_prefix='/api2',
                                allow_to_many_replacement=True)
        data = {
            'data': {
                'type': 'article',
                'id': '1',
                'relationships': {
                    'tags': {
                        'data': [
                            {'type': 'tag', 'id': '1'},
                            {'type': 'tag', 'id': '2'}
                        ]
                    }
                }
            }
        }
        response = self.app.patch('/api2/article/1', data=dumps(data))
        assert response.status_code == 204
        assert [tag1, tag2] == sorted(article.tags, key=lambda t: t.id)


class TestFlaskSQLAlchemy(FlaskSQLAlchemyTestBase):
    """Tests for updating resources defined as Flask-SQLAlchemy models instead
    of pure SQLAlchemy models.

    """

    def setUp(self):
        """Creates the Flask-SQLAlchemy database and models."""
        super(TestFlaskSQLAlchemy, self).setUp()
        if not has_flask_sqlalchemy:
            self.skipTest('Flask-SQLAlchemy not found.')
        # HACK During testing, we don't want the session to expire, so that we
        # can access attributes of model instances *after* a request has been
        # made (that is, after Flask-Restless does its work and commits the
        # session).
        session_options = dict(expire_on_commit=False)
        # Overwrite the `db` and `session` attributes from the superclass.
        self.db = SQLAlchemy(self.flaskapp, session_options=session_options)
        self.session = self.db.session

        class Person(self.db.Model):
            id = self.db.Column(self.db.Integer, primary_key=True)
            name = self.db.Column(self.db.Unicode)

        self.Person = Person
        self.db.create_all()
        self.manager = APIManager(self.flaskapp, session=self.db.session)
        self.manager.create_api(self.Person, methods=['PATCH'])

    def test_create(self):
        """Tests for creating a resource."""
        person = self.Person(id=1, name=u'foo')
        self.session.add(person)
        self.session.commit()
        data = {
            'data': {
                'id': '1',
                'type': 'person',
                'attributes': {
                    'name': u'bar'
                }
            }
        }
        response = self.app.patch('/api/person/1', data=dumps(data))
        assert response.status_code == 204
        assert person.name == 'bar'
