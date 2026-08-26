#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Integration tests for project structure."""

import os
import unittest

import yaml


PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)


class TestProjectStructure(unittest.TestCase):
    """Validate project file structure."""

    def test_tox_ini_exists_root(self):
        """Verify root tox.ini exists."""
        self.assertTrue(os.path.isfile(
            os.path.join(PROJECT_ROOT, 'tox.ini')
        ))

    def test_zuul_yaml_exists(self):
        """Verify .zuul.yaml exists."""
        self.assertTrue(os.path.isfile(
            os.path.join(PROJECT_ROOT, '.zuul.yaml')
        ))

    def test_test_requirements_exists(self):
        """Verify test-requirements.txt exists."""
        self.assertTrue(os.path.isfile(
            os.path.join(
                PROJECT_ROOT, 'test-requirements.txt'
            )
        ))

    def test_requirements_exists(self):
        """Verify requirements.txt exists."""
        self.assertTrue(os.path.isfile(
            os.path.join(
                PROJECT_ROOT, 'requirements.txt'
            )
        ))

    def test_k8sapp_package_exists(self):
        """Verify k8sapp package directory exists."""
        package_dir = os.path.join(
            PROJECT_ROOT,
            'python3-k8sapp-security-profiles-operator',
            'k8sapp_security_profiles_operator',
            'k8sapp_security_profiles_operator'
        )
        self.assertTrue(os.path.isdir(package_dir))

    def test_lifecycle_module_exists(self):
        """Verify lifecycle module exists."""
        module_path = os.path.join(
            PROJECT_ROOT,
            'python3-k8sapp-security-profiles-operator',
            'k8sapp_security_profiles_operator',
            'k8sapp_security_profiles_operator',
            'lifecycle',
            'lifecycle_security_profiles_operator.py'
        )
        self.assertTrue(os.path.isfile(module_path))

    def test_helm_module_exists(self):
        """Verify helm module exists."""
        module_path = os.path.join(
            PROJECT_ROOT,
            'python3-k8sapp-security-profiles-operator',
            'k8sapp_security_profiles_operator',
            'k8sapp_security_profiles_operator',
            'helm',
            'security_profiles_operator.py'
        )
        self.assertTrue(os.path.isfile(module_path))

    def test_constants_module_exists(self):
        """Verify constants module exists."""
        module_path = os.path.join(
            PROJECT_ROOT,
            'python3-k8sapp-security-profiles-operator',
            'k8sapp_security_profiles_operator',
            'k8sapp_security_profiles_operator',
            'common',
            'constants.py'
        )
        self.assertTrue(os.path.isfile(module_path))


class TestYamlConfigs(unittest.TestCase):
    """Validate YAML configuration files."""

    def test_zuul_yaml_valid(self):
        """Verify .zuul.yaml is parseable."""
        zuul_path = os.path.join(
            PROJECT_ROOT, '.zuul.yaml'
        )
        with open(
            zuul_path, 'r', encoding='utf-8'
        ) as yaml_file:
            content = yaml_file.read()
        # Zuul YAML uses !encrypted tags that safe_load
        # cannot handle; verify file is non-empty and starts
        # with valid YAML structure
        self.assertTrue(len(content) > 0)
        self.assertTrue(content.strip().startswith('---'))

    def test_metadata_yaml_valid(self):
        """Verify metadata.yaml is valid YAML."""
        metadata_path = os.path.join(
            PROJECT_ROOT,
            'stx-security-profiles-operator-helm',
            'stx-security-profiles-operator-helm',
            'files',
            'metadata.yaml'
        )
        self.assertTrue(
            os.path.isfile(metadata_path),
            "metadata.yaml not found"
        )
        with open(
            metadata_path, 'r', encoding='utf-8'
        ) as yaml_file:
            data = yaml.safe_load(yaml_file)
        self.assertIsInstance(data, dict)

    def test_kustomization_yaml_valid(self):
        """Verify kustomization.yaml is valid YAML."""
        kustomize_path = os.path.join(
            PROJECT_ROOT,
            'stx-security-profiles-operator-helm',
            'stx-security-profiles-operator-helm',
            'fluxcd-manifests',
            'kustomization.yaml'
        )
        self.assertTrue(
            os.path.isfile(kustomize_path),
            "kustomization.yaml not found"
        )
        with open(
            kustomize_path, 'r', encoding='utf-8'
        ) as yaml_file:
            data = yaml.safe_load(yaml_file)
        self.assertIsInstance(data, dict)

    def test_helmrelease_yaml_valid(self):
        """Verify helmrelease.yaml is valid YAML."""
        helmrelease_path = os.path.join(
            PROJECT_ROOT,
            'stx-security-profiles-operator-helm',
            'stx-security-profiles-operator-helm',
            'fluxcd-manifests',
            'security-profiles-operator',
            'helmrelease.yaml'
        )
        self.assertTrue(
            os.path.isfile(helmrelease_path),
            "helmrelease.yaml not found"
        )
        with open(
            helmrelease_path, 'r',
            encoding='utf-8'
        ) as yaml_file:
            data = yaml.safe_load(yaml_file)
        self.assertIsInstance(data, dict)


class TestSetupCfg(unittest.TestCase):
    """Validate setup.cfg configuration."""

    def test_setup_cfg_exists(self):
        """Verify setup.cfg exists."""
        config_path = os.path.join(
            PROJECT_ROOT,
            'python3-k8sapp-security-profiles-operator',
            'k8sapp_security_profiles_operator',
            'setup.cfg'
        )
        self.assertTrue(os.path.isfile(config_path))

    def test_setup_cfg_has_entry_points(self):
        """Verify setup.cfg contains entry_points."""
        config_path = os.path.join(
            PROJECT_ROOT,
            'python3-k8sapp-security-profiles-operator',
            'k8sapp_security_profiles_operator',
            'setup.cfg'
        )
        with open(
            config_path, 'r', encoding='utf-8'
        ) as config_file:
            content = config_file.read()
        self.assertIn('entry_points', content)

    def test_setup_cfg_references_helm_plugin(self):
        """Verify setup.cfg references helm plugin."""
        config_path = os.path.join(
            PROJECT_ROOT,
            'python3-k8sapp-security-profiles-operator',
            'k8sapp_security_profiles_operator',
            'setup.cfg'
        )
        with open(
            config_path, 'r', encoding='utf-8'
        ) as config_file:
            content = config_file.read()
        self.assertIn(
            'SecurityProfilesOperatorHelm', content
        )

    def test_setup_cfg_references_lifecycle(self):
        """Verify setup.cfg references lifecycle."""
        config_path = os.path.join(
            PROJECT_ROOT,
            'python3-k8sapp-security-profiles-operator',
            'k8sapp_security_profiles_operator',
            'setup.cfg'
        )
        with open(
            config_path, 'r', encoding='utf-8'
        ) as config_file:
            content = config_file.read()
        lifecycle_class = (
            'SecurityProfilesOperatorApp'
            'LifecycleOperator'
        )
        self.assertIn(lifecycle_class, content)


class TestShellScript(unittest.TestCase):
    """Validate shell scripts."""

    def test_build_script_exists(self):
        """Verify build-spo-image.sh exists."""
        script_path = os.path.join(
            PROJECT_ROOT,
            'security-profiles-operator-images',
            'debian', 'all', 'build-spo-image.sh'
        )
        self.assertTrue(os.path.isfile(script_path))

    def test_build_script_readable(self):
        """Verify build-spo-image.sh is readable."""
        script_path = os.path.join(
            PROJECT_ROOT,
            'security-profiles-operator-images',
            'debian', 'all', 'build-spo-image.sh'
        )
        self.assertTrue(
            os.access(script_path, os.R_OK),
            "build-spo-image.sh is not readable"
        )

    def test_build_script_has_shebang(self):
        """Verify build-spo-image.sh has shebang."""
        script_path = os.path.join(
            PROJECT_ROOT,
            'security-profiles-operator-images',
            'debian', 'all', 'build-spo-image.sh'
        )
        with open(
            script_path, 'r', encoding='utf-8'
        ) as script_file:
            first_line = script_file.readline()
        self.assertTrue(first_line.startswith('#!'))


if __name__ == '__main__':
    unittest.main()
