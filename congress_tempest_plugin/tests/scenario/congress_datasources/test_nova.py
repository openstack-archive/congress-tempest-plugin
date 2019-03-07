# Copyright 2014 OpenStack Foundation
# All Rights Reserved.
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

import testtools

from tempest.common import utils
from tempest import config
from tempest.lib.common.utils import test_utils
from tempest.lib import decorators
from tempest.lib import exceptions

from congress_tempest_plugin.tests.scenario import helper
from congress_tempest_plugin.tests.scenario import manager_congress

CONF = config.CONF


class TestNovaDriver(manager_congress.ScenarioPolicyBase):

    @classmethod
    def skip_checks(cls):
        super(TestNovaDriver, cls).skip_checks()
        if not CONF.service_available.nova:
            skip_msg = ("%s skipped as nova is not available" % cls.__name__)
            raise cls.skipException(skip_msg)

        if not (CONF.network.project_networks_reachable or
                CONF.network.public_network_id):
            msg = ('Either project_networks_reachable must be "true", or '
                   'public_network_id must be defined.')
            cls.enabled = False
            raise cls.skipException(msg)

        if not CONF.congress_feature_enabled.nova_driver:
            # queens flag for skipping nova driver tests because
            # congress nova driver in queens does not work with the new
            # novaclient 10.1.0 now part of upper-constraints
            # https://review.openstack.org/#/c/571540/
            msg = 'Nova driver not available.'
            raise cls.skipException(msg)

    def setUp(self):
        super(TestNovaDriver, self).setUp()
        self.keypairs = {}
        self.servers = []
        self.datasource_id = manager_congress.get_datasource_id(
            self.os_admin.congress_client, 'nova')
        self._setup_network_and_servers()

    @decorators.attr(type='smoke')
    @utils.services('compute', 'network')
    def test_nova_datasource_driver_servers(self):
        server_schema = (
            self.os_admin.congress_client.show_datasource_table_schema(
                self.datasource_id, 'servers')['columns'])

        # Convert some of the column names.

        def convert_col(col):
            if col == 'host_id':
                return 'hostId'
            elif col == 'image_id':
                return 'image'
            elif col == 'flavor_id':
                return 'flavor'
            elif col == 'created_at':
                return 'created'
            elif col == 'zone':
                return 'OS-EXT-AZ:availability_zone'
            elif col == 'host_name':
                return 'OS-EXT-SRV-ATTR:hypervisor_hostname'
            else:
                return col

        keys_servers = [convert_col(c['name']) for c in server_schema]

        @helper.retry_on_exception
        def _check_data_table_nova_servers():
            results = (
                self.os_admin.congress_client.list_datasource_rows(
                    self.datasource_id, 'servers'))
            for row in results['results']:
                match = True
                for index in range(len(keys_servers)):
                    if keys_servers[index] in ['image', 'flavor']:
                        val = self.servers[0][keys_servers[index]]['id']
                    # Test servers created doesn't have this attribute,
                    # so ignoring the same in tempest tests.
                    elif keys_servers[index] in \
                            ['OS-EXT-SRV-ATTR:hypervisor_hostname']:
                        continue
                    else:
                        val = self.servers[0][keys_servers[index]]

                    if row['data'][index] != val:
                        match = False
                        break
                if match:
                    return True
            return False

        if not test_utils.call_until_true(func=_check_data_table_nova_servers,
                                          duration=100, sleep_for=5):
            raise exceptions.TimeoutException("Data did not converge in time "
                                              "or failure in server")

    @decorators.attr(type='smoke')
    @utils.services('compute', 'network')
    @testtools.skipUnless(
        CONF.congress_feature_enabled.nova_servers_addresses_table,
        'test checks nova server addresses added in stein')
    def test_nova_datasource_driver_servers_addresses(self):
        server_addresses_schema = (
            self.os_admin.congress_client.show_datasource_table_schema(
                self.datasource_id, 'servers.addresses')['columns'])

        def convert_col(col):
            if col == 'server_id':
                return 'id'
            elif col == 'address':
                return 'addr'
            elif col == 'mac_address':
                return 'OS-EXT-IPS-MAC:mac_addr'
            elif col == 'address_type':
                return 'OS-EXT-IPS:type'
            else:
                return col

        @helper.retry_on_exception
        def _check_data_table_nova_servers_addresses():
            # Note(Akhil): Right now comparing data of only one server we are
            # creating in test. Which in future will be tested on all servers.

            # updating self.servers after associating floating ip to it
            self.servers[0] = self.show_server(self.servers[0]['id'])
            addresses = self.servers[0]['addresses']
            # according to current test server created there is only
            # one network attached. On changing test server following
            # method of getting network name must be updated
            network_name = list(addresses.keys())[0]

            # checks if floating ip is updated in self.servers,
            # alongside fixed ip
            if len(addresses[network_name]) != 2:
                return False

            keys = [convert_col(c['name']) for c in server_addresses_schema]
            results = (
                self.os_admin.congress_client.list_datasource_rows(
                    self.datasource_id, 'servers.addresses'))

            # Note: Below section is checking that every address in addresses
            # is reflected in results['results']
            match = True
            # traversing addresses of test server from nova service
            for address in addresses[network_name]:
                # traversing server addresses from congress nova datasource
                for row in results['results']:
                    for index in range(len(keys)):
                        if keys[index] == 'id':
                            val = self.servers[0]['id']
                        elif keys[index] == 'network_name':
                            val = network_name
                        else:
                            val = address[keys[index]]

                        if row['data'][index] != val:
                            match = False
                            break
                        match = True
                    if match:
                        break
                if not match:
                    return False
            if match:
                return True
            return False
        if not test_utils.call_until_true(
                func=_check_data_table_nova_servers_addresses,
                duration=100, sleep_for=5):
            raise exceptions.TimeoutException("Data did not converge in time "
                                              "or failure in server")

    @decorators.attr(type='smoke')
    @utils.services('compute', 'network')
    def test_nova_datasource_driver_flavors(self):

        @helper.retry_on_exception
        def _check_data_table_nova_flavors():
            # Fetch data from nova each time, because this test may start
            # before nova has all the users.
            flavors = self.flavors_client.list_flavors(detail=True)
            flavor_id_map = {}
            for flavor in flavors['flavors']:
                flavor_id_map[flavor['id']] = flavor

            results = (
                self.os_admin.congress_client.list_datasource_rows(
                    self.datasource_id, 'flavors'))
            # TODO(alexsyip): Not sure what the following OS-FLV-EXT-DATA:
            # prefix is for.
            keys = ['id', 'name', 'vcpus', 'ram', 'disk',
                    'OS-FLV-EXT-DATA:ephemeral', 'rxtx_factor']
            for row in results['results']:
                match = True
                try:
                    flavor_row = flavor_id_map[row['data'][0]]
                except KeyError:
                    return False
                for index in range(len(keys)):
                    if row['data'][index] != flavor_row[keys[index]]:
                        match = False
                        break
                if match:
                    return True
            return False

        if not test_utils.call_until_true(func=_check_data_table_nova_flavors,
                                          duration=100, sleep_for=5):
            raise exceptions.TimeoutException("Data did not converge in time "
                                              "or failure in server")

    @decorators.attr(type='smoke')
    def test_update_no_error(self):
        if not test_utils.call_until_true(
                func=lambda: self.check_datasource_no_error('nova'),
                duration=30, sleep_for=5):
            raise exceptions.TimeoutException('Datasource could not poll '
                                              'without error.')
