# Playlist Helper Makefile
# Build and development tasks

.PHONY: run install deps build-exe build-rpm clean

# Default target
all: deps

# Install Python dependencies
install:
	pip install -r requirements.txt

# Install development dependencies
dev-deps: install
	pip install pyinstaller build

# Run the application
run:
	python main.py

# Build Windows executable (requires PyInstaller + Windows or cross-compile setup)
build-exe:
	python build_exe.py --onefile

# Build RPM package (requires Fedora/RHEL with rpmbuild)
build-rpm:
	@echo "Building RPM package..."
	@if command -v rpmbuild >/dev/null 2>&1; then \
		python setup.py sdist --format=gztar; \
		cp dist/playlist-helper-*.tar.gz ~/rpmbuild/SOURCES/; \
		rpmbuild -ba playlist-helper.spec; \
		echo "RPM built in ~/rpmbuild/RPMS/"; \
	else \
		echo "rpmbuild not found. Install with: sudo dnf install rpm-build"; \
	fi

# Build Debian package (alternative for Debian/Ubuntu)
build-deb:
	@echo "Building Debian package..."
	@if command -v dpkg-deb >/dev/null 2>&1; then \
		python setup.py sdist --format=gztar; \
		echo "Use dh_make + dpkg-buildpackage for .deb"; \
		echo "Or install with: pip install . && python setup.py --command-packages=stdeb.command bdist_deb"; \
	else \
		echo "dpkg-deb not found. This system uses RPM (Fedora)."; \
		echo "For .deb, build on Debian/Ubuntu with: python setup.py --command-packages=stdeb.command bdist_deb"; \
	fi

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info/ __pycache__/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
