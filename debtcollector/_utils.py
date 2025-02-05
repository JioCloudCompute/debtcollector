# -*- coding: utf-8 -*-

#    Copyright (C) 2015 Yahoo! Inc. All Rights Reserved.
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

import inspect
import types
import warnings

import six

try:
    _TYPE_TYPE = types.TypeType
except AttributeError:
    _TYPE_TYPE = type


# See: https://docs.python.org/2/library/__builtin__.html#module-__builtin__
# and see https://docs.python.org/2/reference/executionmodel.html (and likely
# others)...
_BUILTIN_MODULES = ('builtins', '__builtin__', '__builtins__', 'exceptions')
_enabled = True


def deprecation(message, stacklevel=None, category=None):
    """Warns about some type of deprecation that has been (or will be) made.

    This helper function makes it easier to interact with the warnings module
    by standardizing the arguments that the warning function recieves so that
    it is easier to use.

    This should be used to emit warnings to users (users can easily turn these
    warnings off/on, see https://docs.python.org/2/library/warnings.html
    as they see fit so that the messages do not fill up the users logs with
    warnings that they do not wish to see in production) about functions,
    methods, attributes or other code that is deprecated and will be removed
    in a future release (this is done using these warnings to avoid breaking
    existing users of those functions, methods, code; which a library should
    avoid doing by always giving at *least* N + 1 release for users to address
    the deprecation warnings).
    """
    if not _enabled:
        return
    if category is None:
        category = DeprecationWarning
    if stacklevel is None:
        warnings.warn(message, category=category)
    else:
        warnings.warn(message, category=category, stacklevel=stacklevel)


def get_qualified_name(obj):
    # Prefer the py3.x name (if we can get at it...)
    try:
        return (True, obj.__qualname__)
    except AttributeError:
        return (False, obj.__name__)


def generate_message(prefix, postfix=None, message=None,
                     version=None, removal_version=None):
    """Helper to generate a common message 'style' for deprecation helpers."""
    message_components = [prefix]
    if version:
        message_components.append(" in version '%s'" % version)
    if removal_version:
        if removal_version == "?":
            message_components.append(" and will be removed in a future"
                                      " version")
        else:
            message_components.append(" and will be removed in version '%s'"
                                      % removal_version)
    if postfix:
        message_components.append(postfix)
    if message:
        message_components.append(": %s" % message)
    return ''.join(message_components)


def get_class_name(obj, fully_qualified=True):
    """Get class name for object.

    If object is a type, fully qualified name of the type is returned.
    Else, fully qualified name of the type of the object is returned.
    For builtin types, just name is returned.
    """
    if not isinstance(obj, six.class_types):
        obj = type(obj)
    try:
        built_in = obj.__module__ in _BUILTIN_MODULES
    except AttributeError:
        pass
    else:
        if built_in:
            return obj.__name__

    if fully_qualified and hasattr(obj, '__module__'):
        return '%s.%s' % (obj.__module__, obj.__name__)
    else:
        return obj.__name__


def get_method_self(method):
    """Gets the ``self`` object attached to this method (or none)."""
    if not inspect.ismethod(method):
        return None
    try:
        return six.get_method_self(method)
    except AttributeError:
        return None


def get_callable_name(function):
    """Generate a name from callable.

    Tries to do the best to guess fully qualified callable name.
    """
    method_self = get_method_self(function)
    if method_self is not None:
        # This is a bound method.
        if isinstance(method_self, six.class_types):
            # This is a bound class method.
            im_class = method_self
        else:
            im_class = type(method_self)
        try:
            parts = (im_class.__module__, function.__qualname__)
        except AttributeError:
            parts = (im_class.__module__, im_class.__name__, function.__name__)
    elif inspect.ismethod(function) or inspect.isfunction(function):
        # This could be a function, a static method, a unbound method...
        try:
            parts = (function.__module__, function.__qualname__)
        except AttributeError:
            if hasattr(function, 'im_class'):
                # This is a unbound method, which exists only in python 2.x
                im_class = function.im_class
                parts = (im_class.__module__,
                         im_class.__name__, function.__name__)
            else:
                parts = (function.__module__, function.__name__)
    else:
        im_class = type(function)
        if im_class is _TYPE_TYPE:
            im_class = function
        try:
            parts = (im_class.__module__, im_class.__qualname__)
        except AttributeError:
            parts = (im_class.__module__, im_class.__name__)
    # When running under sphinx it appears this can be none? if so just
    # don't include it...
    mod, rest = (parts[0], parts[1:])
    if not mod:
        return '.'.join(rest)
    else:
        return '.'.join(parts)
