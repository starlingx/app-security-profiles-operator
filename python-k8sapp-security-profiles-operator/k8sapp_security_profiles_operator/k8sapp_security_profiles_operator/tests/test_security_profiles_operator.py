# Copyright (c) 2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from k8sapp_security_profiles_operator.tests import test_plugins

from sysinv.db import api as dbapi
from sysinv.tests.db import utils as dbutils
from sysinv.tests.helm import base


class SecurityProfilesOperatorTestCase(test_plugins.K8SAppSecurityProfilesOperatorAppMixin,
                         base.HelmTestCaseMixin):

    def setUp(self):
        super(SecurityProfilesOperatorTestCase, self).setUp()
        self.app = dbutils.create_test_app(name='security-profiles-operator')
        self.dbapi = dbapi.get_instance()
