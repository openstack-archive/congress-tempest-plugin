# Copyright 2015 Intel Corp
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

from oslo_config import cfg

from tempest import config  # noqa


service_available_group = cfg.OptGroup(name="service_available",
                                       title="Available OpenStack Services")
ServiceAvailableGroup = [
    cfg.BoolOpt('congress',
                default=True,
                help="Whether or not Congress is expected to be available"),
]

congress_feature_group = cfg.OptGroup(name="congress-feature-enabled",
                                      title="Congress Feature Flags")
CongressFeatureGroup = [
    cfg.BoolOpt('monasca_webhook',
                default=False,
                help="monasca_webhook feature available"),
    cfg.BoolOpt('monasca_webhook_rocky',
                default=False,
                help="monasca_webhook uses Rocky schema"),
    cfg.BoolOpt('vitrage_webhook',
                default=False,
                help="vitrage_webhook feature available"),
    cfg.BoolOpt('nova_driver',
                default=True,
                help="nova driver feature available"),
    cfg.BoolOpt('nova_servers_addresses_table',
                default=True,
                help="nova driver servers.addresses table available"),
]

congressha_group = cfg.OptGroup(name="congressha", title="Congress HA Options")

CongressHAGroup = [
    cfg.StrOpt("replica_type",
               default="policyha",
               help="service type used to create a replica congress server."),
    cfg.IntOpt("replica_port",
               default=4001,
               help="The listening port for a replica congress server. "),
]

congressz3_group = cfg.OptGroup(name="congressz3", title="Congress Z3 Options")

CongressZ3Group = [
    cfg.BoolOpt('enabled',
                default=False,
                help="Whether Z3 is installed or not for Congress"),
    cfg.BoolOpt('support_builtins',
                default=True,
                help="builtins supported by Z3 engine"),
]
