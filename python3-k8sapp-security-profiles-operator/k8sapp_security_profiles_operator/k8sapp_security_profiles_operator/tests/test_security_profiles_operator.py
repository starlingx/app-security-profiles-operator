# Copyright (c) 2023,2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from unittest import mock

from k8sapp_security_profiles_operator.lifecycle import (
    lifecycle_security_profiles_operator as lifecycle)
from k8sapp_security_profiles_operator.tests import test_plugins

from sysinv.common import constants
from sysinv.db import api as dbapi
from sysinv.tests import base as sysinv_base
from sysinv.tests.helm import base
from sysinv.tests.db import base as dbbase
from sysinv.tests.db import utils as dbutils


class SecurityProfilesOperatorTestCase(test_plugins.K8SAppSecurityProfilesOperatorAppMixin,
                                       base.HelmTestCaseMixin):

    def setUp(self):
        super(SecurityProfilesOperatorTestCase, self).setUp()
        self.app = dbutils.create_test_app(name='security-profiles-operator')
        self.dbapi = dbapi.get_instance()


class SecurityProfilesOperatorTestCaseDummy(SecurityProfilesOperatorTestCase,
                                            dbbase.ProvisionedControllerHostTestCase):

    def test_dummy(self):
        pass


class SpodSchedulingTestCase(sysinv_base.TestCase):
    """Unit tests for _spod_scheduling system-type aware tolerations.

    The SPOD CR must keep spod off the controllers on Standard systems, where
    AppArmor is disabled, and must keep spod on the controllers on All-in-one
    systems, where the controllers are also the workers. An empty tolerations
    list is treated as unset by the operator, so the block must be an explicit
    non-empty list.
    """

    def setUp(self):
        super(SpodSchedulingTestCase, self).setUp()
        self.op = lifecycle.SecurityProfilesOperatorAppLifecycleOperator()

    @staticmethod
    def _dbapi_with_system_type(system_type):
        db = mock.Mock()
        db.isystem_get_one.return_value = mock.Mock(system_type=system_type)
        return db

    @staticmethod
    def _toleration_keys(scheduling):
        return {t['key'] for t in scheduling['tolerations']}

    def test_standard_omits_control_plane_toleration(self):
        # On Standard, spod must be repelled from the control-plane nodes, so
        # the control-plane toleration must be absent and the list non-empty.
        db = self._dbapi_with_system_type(constants.TIS_STD_BUILD)
        scheduling = self.op._spod_scheduling(db)
        keys = self._toleration_keys(scheduling)
        self.assertIn('node.kubernetes.io/not-ready', keys)
        self.assertNotIn('node-role.kubernetes.io/control-plane', keys)
        self.assertNotIn('node-role.kubernetes.io/master', keys)
        self.assertTrue(scheduling['tolerations'])

    def test_aio_tolerates_control_plane(self):
        # On All-in-one, the controllers are the workers, so spod must tolerate
        # the control-plane taint and run there.
        db = self._dbapi_with_system_type(constants.TIS_AIO_BUILD)
        scheduling = self.op._spod_scheduling(db)
        keys = self._toleration_keys(scheduling)
        self.assertIn('node-role.kubernetes.io/control-plane', keys)
        self.assertIn('node-role.kubernetes.io/master', keys)
        self.assertIn('node.kubernetes.io/not-ready', keys)

    def test_unknown_system_type_fails_safe_to_tolerate_control_plane(self):
        # If the system type cannot be read, keep the previous behaviour of
        # tolerating the control-plane taint rather than risk repelling spod
        # from every node.
        db = mock.Mock()
        db.isystem_get_one.side_effect = Exception("db unavailable")
        scheduling = self.op._spod_scheduling(db)
        keys = self._toleration_keys(scheduling)
        self.assertIn('node-role.kubernetes.io/control-plane', keys)
