# Copyright (c) 2015 Hewlett Packard. All rights reserved.
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
#

import os

import tenacity


def retry_check_function_return_value_condition(
        f, check_condition, error_msg=None, retry_interval=1,
        retry_attempts=20):
    """Check if function f returns value s.t check_condition(value) is True."""

    @tenacity.retry(stop=tenacity.stop_after_attempt(retry_attempts),
                    wait=tenacity.wait_fixed(retry_interval))
    def retried_function():
        r = f()
        if not check_condition(r):
            raise Exception(error_msg or
                            'Actual return value ({}) does not satisfy '
                            'provided condition'.format(r))
        return r

    return retried_function()


def retry_check_function_return_value(f, expected_value, error_msg=None):
    """Check if function f returns expected value."""
    if not error_msg:
        error_msg = 'Expected value "%s" not found' % expected_value
    retry_check_function_return_value_condition(
        f, lambda v: v == expected_value, error_msg)


def retry_on_exception(f):
    """Decorator to retry on an exception."""
    def wrapper():
        try:
            return f()
        except Exception:
            return False
    return wrapper


def root_path():
    """Return path to root of source code."""
    x = os.path.realpath(__file__)
    x, y = os.path.split(x)  # drop "helper.py"
    x, y = os.path.split(x)  # drop "scenario"
    x, y = os.path.split(x)  # drop "tests"
    x, y = os.path.split(x)  # drop "congress_tempest_plugin"
    return x
