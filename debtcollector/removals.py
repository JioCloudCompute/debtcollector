# Copyright 2014 Hewlett-Packard Development Company, L.P.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import functools
import inspect

import six
import wrapt

from debtcollector import _utils


def _get_qualified_name(obj):
    return _utils.get_qualified_name(obj)[1]


def _fetch_first_result(fget, fset, fdel, apply_func, value_not_found=None):
    """Fetch first non-none/empty result of applying ``apply_func``."""
    for f in filter(None, (fget, fset, fdel)):
        result = apply_func(f)
        if result:
            return result
    return value_not_found


class removed_property(object):
    """Property descriptor that deprecates a property.

    This works like the ``@property`` descriptor but can be used instead to
    provide the same functionality and also interact with the :mod:`warnings`
    module to warn when a property is accessed, set and/or deleted.

    :param message: string used as ending contents of the deprecate message
    :param version: version string (represents the version this deprecation
                    was created in)
    :param removal_version: version string (represents the version this
                            deprecation will be removed in); a string
                            of '?' will denote this will be removed in
                            some future unknown version
    :param stacklevel: stacklevel used in the :func:`warnings.warn` function
                       to locate where the users code is when reporting the
                       deprecation call (the default being 3)
    :param category: the :mod:`warnings` category to use, defaults to
                     :py:class:`DeprecationWarning` if not provided
    """

    # Message templates that will be turned into real messages as needed.
    _PROPERTY_GONE_TPLS = {
        'set': "Setting the '%s' property is deprecated",
        'get': "Reading the '%s' property is deprecated",
        'delete': "Deleting the '%s' property is deprecated",
    }

    def __init__(self, fget=None, fset=None, fdel=None, doc=None,
                 stacklevel=3, category=DeprecationWarning,
                 version=None, removal_version=None, message=None):
        self.fset = fset
        self.fget = fget
        self.fdel = fdel
        self.stacklevel = stacklevel
        self.category = category
        self.version = version
        self.removal_version = removal_version
        self.message = message
        if doc is None and inspect.isfunction(fget):
            doc = getattr(fget, '__doc__', None)
        self._message_cache = {}
        self.__doc__ = doc

    def _fetch_message_from_cache(self, kind):
        try:
            out_message = self._message_cache[kind]
        except KeyError:
            prefix_tpl = self._PROPERTY_GONE_TPLS[kind]
            prefix = prefix_tpl % _fetch_first_result(
                self.fget, self.fset, self.fdel, _get_qualified_name,
                value_not_found="???")
            out_message = _utils.generate_message(
                prefix, message=self.message, version=self.version,
                removal_version=self.removal_version)
            self._message_cache[kind] = out_message
        return out_message

    def __call__(self, fget, **kwargs):
        self.fget = fget
        self.message = kwargs.get('message', self.message)
        self.version = kwargs.get('version', self.version)
        self.removal_version = kwargs.get('removal_version',
                                          self.removal_version)
        self.stacklevel = kwargs.get('stacklevel', self.stacklevel)
        self.category = kwargs.get('category', self.category)
        self.__doc__ = kwargs.get('doc',
                                  getattr(fget, '__doc__', self.__doc__))
        # Regenerate all the messages...
        self._message_cache.clear()
        return self

    def __delete__(self, obj):
        if self.fdel is None:
            raise AttributeError("can't delete attribute")
        out_message = self._fetch_message_from_cache('delete')
        _utils.deprecation(out_message, stacklevel=self.stacklevel,
                           category=self.category)
        self.fdel(obj)

    def __set__(self, obj, value):
        if self.fset is None:
            raise AttributeError("can't set attribute")
        out_message = self._fetch_message_from_cache('set')
        _utils.deprecation(out_message, stacklevel=self.stacklevel,
                           category=self.category)
        self.fset(obj, value)

    def __get__(self, obj, value):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError("unreadable attribute")
        out_message = self._fetch_message_from_cache('get')
        _utils.deprecation(out_message, stacklevel=self.stacklevel,
                           category=self.category)
        return self.fget(obj)

    def getter(self, fget):
        o = type(self)(fget, self.fset, self.fdel, self.__doc__)
        o.message = self.message
        o.version = self.version
        o.stacklevel = self.stacklevel
        o.removal_version = self.removal_version
        o.category = self.category
        return o

    def setter(self, fset):
        o = type(self)(self.fget, fset, self.fdel, self.__doc__)
        o.message = self.message
        o.version = self.version
        o.stacklevel = self.stacklevel
        o.removal_version = self.removal_version
        o.category = self.category
        return o

    def deleter(self, fdel):
        o = type(self)(self.fget, self.fset, fdel, self.__doc__)
        o.message = self.message
        o.version = self.version
        o.stacklevel = self.stacklevel
        o.removal_version = self.removal_version
        o.category = self.category
        return o


def remove(f=None, message=None, version=None, removal_version=None,
           stacklevel=3, category=None):
    """Decorates a function, method, or class to emit a deprecation warning

    Due to limitations of the wrapt library (and python) itself, if this
    is applied to subclasses of metaclasses then it likely will not work
    as expected. More information can be found at bug #1520397 to see if
    this situation affects your usage of this *universal* decorator.

    :param str message: A message to include in the deprecation warning
    :param str version: Specify what version the removed function is present in
    :param str removal_version: What version the function will be removed. If
                                '?' is used this implies an undefined future
                                version
    :param int stacklevel: How many entries deep in the call stack before
                           ignoring
    :param type category: warnings message category (this defaults to
                          ``DeprecationWarning`` when none is provided)
    """
    if f is None:
        return functools.partial(remove, message=message,
                                 version=version,
                                 removal_version=removal_version,
                                 stacklevel=stacklevel,
                                 category=category)

    @wrapt.decorator
    def wrapper(f, instance, args, kwargs):
        qualified, f_name = _utils.get_qualified_name(f)
        if qualified:
            if inspect.isclass(f):
                prefix_pre = "Using class"
                thing_post = ''
            else:
                prefix_pre = "Using function/method"
                thing_post = '()'
        if not qualified:
            prefix_pre = "Using function/method"
            base_name = None
            if instance is None:
                # Decorator was used on a class
                if inspect.isclass(f):
                    prefix_pre = "Using class"
                    thing_post = ''
                    module_name = _get_qualified_name(inspect.getmodule(f))
                    if module_name == '__main__':
                        f_name = _utils.get_class_name(
                            f, fully_qualified=False)
                    else:
                        f_name = _utils.get_class_name(
                            f, fully_qualified=True)
                # Decorator was a used on a function
                else:
                    thing_post = '()'
                    module_name = _get_qualified_name(inspect.getmodule(f))
                    if module_name != '__main__':
                        f_name = _utils.get_callable_name(f)
            # Decorator was used on a classmethod or instancemethod
            else:
                thing_post = '()'
                base_name = _utils.get_class_name(instance,
                                                  fully_qualified=False)
            if base_name:
                thing_name = ".".join([base_name, f_name])
            else:
                thing_name = f_name
        else:
            thing_name = f_name
        if thing_post:
            thing_name += thing_post
        prefix = prefix_pre + " '%s' is deprecated" % (thing_name)
        out_message = _utils.generate_message(
            prefix,
            version=version,
            removal_version=removal_version,
            message=message)
        _utils.deprecation(out_message,
                           stacklevel=stacklevel, category=category)
        return f(*args, **kwargs)
    return wrapper(f)


def removed_kwarg(old_name, message=None,
                  version=None, removal_version=None, stacklevel=3,
                  category=None):
    """Decorates a kwarg accepting function to deprecate a removed kwarg."""

    prefix = "Using the '%s' argument is deprecated" % old_name
    out_message = _utils.generate_message(
        prefix, postfix=None, message=message, version=version,
        removal_version=removal_version)

    @wrapt.decorator
    def wrapper(f, instance, args, kwargs):
        if old_name in kwargs:
            _utils.deprecation(out_message,
                               stacklevel=stacklevel, category=category)
        return f(*args, **kwargs)

    return wrapper


def removed_module(module, replacement=None, message=None,
                   version=None, removal_version=None, stacklevel=3,
                   category=None):
    """Helper to be called inside a module to emit a deprecation warning

    :param str replacment: A location (or information about) of any potential
                           replacement for the removed module (if applicable)
    :param str message: A message to include in the deprecation warning
    :param str version: Specify what version the removed module is present in
    :param str removal_version: What version the module will be removed. If
                                '?' is used this implies an undefined future
                                version
    :param int stacklevel: How many entries deep in the call stack before
                           ignoring
    :param type category: warnings message category (this defaults to
                          ``DeprecationWarning`` when none is provided)
    """
    if inspect.ismodule(module):
        module_name = _get_qualified_name(module)
    elif isinstance(module, six.string_types):
        module_name = module
    else:
        _qual, type_name = _utils.get_qualified_name(type(module))
        raise TypeError("Unexpected module type '%s' (expected string or"
                        " module type only)" % type_name)
    prefix = "The '%s' module usage is deprecated" % module_name
    if replacement:
        postfix = ", please use %s instead" % replacement
    else:
        postfix = None
    out_message = _utils.generate_message(prefix,
                                          postfix=postfix, message=message,
                                          version=version,
                                          removal_version=removal_version)
    _utils.deprecation(out_message,
                       stacklevel=stacklevel, category=category)
