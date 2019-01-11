# Copyright 2017 Orange. All Rights Reserved.
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

"Tempest tests for config datasource"
import random
import string
import testtools

from tempest import config
from tempest.lib import decorators

from congress_tempest_plugin.tests.scenario import manager_congress

CONF = config.CONF


class TestZ3(manager_congress.ScenarioPolicyBase):
    """Tests for Z3 policies with an actual Z3 engine"""

    @classmethod
    def skip_checks(cls):
        """Checks that Z3 is available"""
        super(TestZ3, cls).skip_checks()
        if not CONF.congressz3.enabled:
            msg = ("%s skipped as z3 is not available" %
                   cls.__class__.__name__)
            raise cls.skipException(msg)

    def _add_policy(self, seed, kind="nonrecursive"):
        "short cut for adding a policy with random name"
        client = self.os_admin.congress_client

        def cleanup(policy_name):
            """Removes the policy"""
            result = client.list_policy_rules(policy_name)
            for rule in result['results']:
                client.delete_policy_rule(policy_name, rule['id'])
            client.delete_policy(policy_name)

        suffix = ''.join(
            random.choice(string.ascii_lowercase)
            for x in range(10))
        policy_name = "%s_%s" % (seed, suffix)
        body = {"name": policy_name, "kind": kind}
        resp = client.create_policy(body)

        self.addCleanup(cleanup, resp['name'])
        return resp['name']

    def _add_rule(self, policy_name, rule):
        """Shortcut to add a rule to a policy"""
        self.os_admin.congress_client.create_policy_rule(
            policy_name, {'rule': rule})

    @decorators.attr(type='smoke')
    def test_z3_recursivity(self):
        """Recursivity in Z3

        This test checks Z3 in isolation on a simple recursive problem.
        """
        computations = self._add_policy("recur", "z3")
        expected = [(1, 2), (1, 3), (1, 4), (1, 5), (1, 6),
                    (2, 3), (2, 4), (2, 5), (2, 6),
                    (4, 5), (4, 6)]
        for pair in [(1, 2), (2, 3), (2, 4), (4, 5), (4, 6)]:
            self._add_rule(computations, 'link(%d, %d)' % pair)

        self._add_rule(computations, 'path(x, y) :- link(x, y)')
        self._add_rule(computations,
                       'path(x, y) :- link(x, z), path(z, y)')
        result = self.os_admin.congress_client.list_policy_rows(
            computations, "path")
        extracted = [(row['data'][0], row['data'][1])
                     for row in result['results']]
        self.assertEqual(expected, sorted(extracted))

    @decorators.attr(type='smoke')
    def test_z3_inter_policies(self):
        """Inter policy call

        This test create a non Z3 policy populate a table.
        This table is used by a Z3 policy to compute a transitive closure
        Another policy will use the computed result and create a result table
        using builtins not available to Z3.
        """
        facts = self._add_policy("fact")
        formatter = self._add_policy("form")
        computations = self._add_policy("comp", "z3")
        expected = []
        for pair in [(1, 2), (2, 3), (2, 4), (4, 5), (4, 6)]:
            self._add_rule(facts, 'link("N%d", "N%d")' % pair)
        for pair in [(1, 2), (1, 3), (1, 4), (1, 5), (1, 6),
                     (2, 3), (2, 4), (2, 5), (2, 6),
                     (4, 5), (4, 6)]:
            expected.append(u'N%d - N%d' % pair)
        self._add_rule(computations, 'path(x, y) :- %s:link(x, y)' % facts)
        self._add_rule(computations,
                       'path(x, y) :- %s:link(x, z), path(z, y)' % facts)
        self._add_rule(
            formatter,
            ('res(x) :- %s:path(y, z), builtin:concat(y, " - ", t), '
             'builtin:concat(t, z, x)') % computations)
        result = self.os_admin.congress_client.list_policy_rows(
            formatter, "res")
        extracted = [row['data'][0] for row in result['results']]
        self.assertEqual(expected, sorted(extracted))

    @decorators.attr(type='smoke')
    @testtools.skipUnless(CONF.congressz3.support_builtins,
                          'Z3 builtins not supported in this version.')
    def test_z3_builtins(self):
        """Basic builtins test

        This test verifies some facts on basic builtins.
        """
        policy = self._add_policy("comp", "z3")
        x = 456
        y = 123
        self._add_rule(policy, 'x(%d)' % x)
        self._add_rule(policy, 'y(%d)' % y)
        self._add_rule(
            policy,
            ('arith(a,b,c,d,e,f) :- x(x), y(y), builtin:plus(x, y, a), '
             'builtin:minus(x, y, b), builtin:mul(x, y, c), '
             'builtin:and(x,y,d), builtin:or(x,y,e), builtin:bnot(x,f)'))
        result = self.os_admin.congress_client.list_policy_rows(
            policy, "arith")
        extracted = [row['data'] for row in result['results']]
        expected = [[x + y, x - y, x * y, x & y, x | y, ~x & 0xffffffff]]
        self.assertEqual(expected, extracted)

    @decorators.attr(type='smoke')
    @testtools.skipUnless(CONF.congressz3.support_builtins,
                          'Z3 builtins not supported in this version.')
    def test_z3_compare_builtins(self):
        """Basic builtins test for comparison

        This test verifies some facts on basic builtins.
        """
        policy = self._add_policy("comp", "z3")
        x = 456
        y = 123
        self._add_rule(policy, 'x(%d)' % x)
        self._add_rule(policy, 'y(%d)' % y)
        checks = [
            ('equal(x,y)', x == y),
            ('equal(x,x)', x == x),
            ('lt(x,y)', x < y),
            ('lt(y,x)', y < x),
            ('lt(x,x)', x < x),
            ('lteq(x,y)', x <= y),
            ('lteq(y,x)', y <= x),
            ('lteq(x,x)', x <= x),
            ('gt(x,y)', x > y),
            ('gt(y,x)', y > x),
            ('gt(x,x)', x > x),
            ('gteq(x,y)', x >= y),
            ('gteq(y,x)', y >= x),
            ('gteq(x,x)', x >= x)
        ]
        for (num, (pred, _)) in enumerate(checks):
            self._add_rule(
                policy,
                ('check(%d) :- x(x), y(y), builtin:%s' % (num, pred)))
        result = self.os_admin.congress_client.list_policy_rows(
            policy, "check")
        extracted = [row['data'][0] for row in result['results']]
        extracted.sort()
        expected = [n for (n, (_, c)) in enumerate(checks) if c]
        self.assertEqual(expected, extracted)
