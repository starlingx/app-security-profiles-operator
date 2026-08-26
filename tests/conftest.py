"""
Test configuration and fixtures for
app-security-profiles-operator.
"""
#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import sys
import types
from unittest import mock

# Ensure project source is importable
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
K8SAPP_ROOT = os.path.join(
    PROJECT_ROOT,
    'python3-k8sapp-security-profiles-operator',
    'k8sapp_security_profiles_operator'
)
if K8SAPP_ROOT not in sys.path:
    sys.path.insert(0, K8SAPP_ROOT)


def _create_stub_module(module_name):
    """Create and register a stub module.

    module_name -- dotted module path to register
    Returns the newly created module object.
    """
    stub = types.ModuleType(module_name)
    sys.modules[module_name] = stub
    return stub


# Create all sysinv stub modules as real module objects
STUB_MODULE_NAMES = [
    'sysinv', 'sysinv.common', 'sysinv.helm',
    'sysinv.helm.lifecycle_utils',
    'sysinv.db', 'sysinv.db.api',
    'sysinv.tests', 'sysinv.tests.helm',
    'sysinv.tests.helm.base', 'sysinv.tests.db',
    'sysinv.tests.db.base', 'sysinv.tests.db.utils',
    'oslo_log',
]
for stub_name in STUB_MODULE_NAMES:
    if stub_name not in sys.modules:
        _create_stub_module(stub_name)

# oslo_log.log
oslo_log_mod = sys.modules['oslo_log']
oslo_log_log_mod = _create_stub_module('oslo_log.log')
oslo_log_log_mod.getLogger = mock.MagicMock(
    return_value=mock.MagicMock()
)
oslo_log_mod.log = oslo_log_log_mod

# sysinv.common.constants
sysinv_constants_mod = _create_stub_module(
    'sysinv.common.constants'
)
sysinv_constants_mod.APP_APPLY_OP = 'apply'
sysinv_constants_mod.APP_REMOVE_OP = 'remove'
sysinv_constants_mod.APP_DOWNGRADE_OP = 'downgrade'

# sysinv.common.exception
exception_mod = _create_stub_module(
    'sysinv.common.exception'
)


class LifecycleMissingInfo(Exception):
    """Raised when lifecycle hook info is incomplete."""


class ApplicationApplyFailure(Exception):
    """Raised when application apply fails."""

    def __init__(self, name=''):
        self.name = name
        super().__init__(name)


class InvalidHelmNamespace(Exception):
    """Raised for invalid helm namespace."""

    def __init__(self, chart='', namespace=''):
        super().__init__(
            '{chart}:{ns}'.format(
                chart=chart, ns=namespace
            )
        )


class HelmOverrideNotFound(Exception):
    """Raised when helm override is not found."""


exception_mod.LifecycleMissingInfo = LifecycleMissingInfo
exception_mod.ApplicationApplyFailure = (
    ApplicationApplyFailure
)
exception_mod.InvalidHelmNamespace = InvalidHelmNamespace
exception_mod.HelmOverrideNotFound = HelmOverrideNotFound

# sysinv.common.kubernetes
kubernetes_mod = _create_stub_module(
    'sysinv.common.kubernetes'
)
kubernetes_mod.KUBERNETES_ADMIN_CONF = (
    '/etc/kubernetes/admin.conf'
)

# sysinv.common.utils
sysinv_utils_mod = _create_stub_module(
    'sysinv.common.utils'
)
sysinv_utils_mod.trycmd = mock.MagicMock(
    return_value=('', '')
)
sysinv_utils_mod.execute = mock.MagicMock(
    return_value=('', '')
)

# sysinv.helm.base
helm_base_mod = _create_stub_module('sysinv.helm.base')


class BaseHelm:
    """Mock BaseHelm for testing."""

    SUPPORTED_NAMESPACES = ['kube-system']
    CHART = ''
    SERVICE_NAME = ''

    def get_namespaces(self):
        """Return supported namespaces."""
        return self.SUPPORTED_NAMESPACES

    def get_overrides(self, namespace=None):
        """Return helm overrides for a namespace."""
        return {}


helm_base_mod.BaseHelm = BaseHelm

# sysinv.helm.lifecycle_base
lifecycle_base_mod = _create_stub_module(
    'sysinv.helm.lifecycle_base'
)


class AppLifecycleOperator:
    """Mock AppLifecycleOperator for testing."""

    def app_lifecycle_actions(self, *args, **kwargs):
        """Handle lifecycle actions."""


lifecycle_base_mod.AppLifecycleOperator = (
    AppLifecycleOperator
)

# sysinv.helm.lifecycle_utils
lifecycle_utils_mod = sys.modules['sysinv.helm.lifecycle_utils']
lifecycle_utils_mod.create_local_registry_secrets = (
    mock.MagicMock()
)
lifecycle_utils_mod.add_pod_security_admission_controller_labels = (
    mock.MagicMock()
)
lifecycle_utils_mod.delete_local_registry_secrets = (
    mock.MagicMock()
)

# sysinv.helm.lifecycle_constants
lifecycle_constants_mod = _create_stub_module(
    'sysinv.helm.lifecycle_constants'
)


class LifecycleConstants:
    """Mock LifecycleConstants for testing."""

    APP_LIFECYCLE_TYPE_FLUXCD_REQUEST = 'fluxcd-request'
    APP_LIFECYCLE_TYPE_OPERATION = 'operation'
    APP_LIFECYCLE_TYPE_RESOURCE = 'resource'
    APP_LIFECYCLE_TYPE_MANIFEST = 'manifest'
    APP_LIFECYCLE_TYPE_SEMANTIC_CHECK = 'check'
    APP_LIFECYCLE_TYPE_RBD = 'rbd'
    APP_LIFECYCLE_MODE_MANUAL = 'manual'
    APP_LIFECYCLE_TIMING_PRE = 'pre'
    APP_LIFECYCLE_TIMING_POST = 'post'
    APP_LIFECYCLE_TIMING_STATUS = 'status'
    EXTRA = 'extra'
    RETURN_CODE = 'return_code'


lifecycle_constants_mod.LifecycleConstants = (
    LifecycleConstants
)
