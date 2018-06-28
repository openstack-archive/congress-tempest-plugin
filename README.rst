===============================
congress-tempest-plugin
===============================

Tempest Plugin for Congress project.
This project covers Tempest tests for Congress project.

* Free software: Apache license
* Documentation: https://docs.openstack.org/congress-tempest-plugin/latest
* Release notes: https://docs.openstack.org/releasenotes/congress/
* Source: https://git.openstack.org/cgit/openstack/congress-tempest-plugin
* Bugs: https://bugs.launchpad.net/congress

Tempest Integration
-------------------

To list all Congress tempest cases, go to tempest directory, then run::

    $ testr list-tests congress

To run congress tempest plugin tests using tox, go to tempest directory, then run::

    $ tox -eall-plugin congress

And, to run a specific test::

    $ tox -eall-plugin congress_tempest_plugin.tests.scenario.test_congress_basic_ops.TestPolicyBasicOps.test_policy_basic_op

