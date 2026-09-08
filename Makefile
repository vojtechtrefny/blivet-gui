APPNAME=blivet-gui
SPECFILE=blivet-gui.spec
VERSION=$(shell awk '/Version:/ { print $$2 }' $(SPECFILE))
RELEASE=$(shell awk '/Release:/ { print $$2 }' $(SPECFILE) | sed -e 's|%.*$$||g')
RELEASE_TAG=$(VERSION)

PYTHON=python3

ANSIBLE_BECOME_FLAG := $(shell [ "$$(id -u)" -eq 0 ] && echo "" || echo "-K")

all:
	$(MAKE) -C po

potfile:
	$(MAKE) -C po potfile

install-requires:
	@echo "*** Installing the dependencies required for testing and analysis ***"
	@which ansible-playbook >/dev/null 2>&1 || ( echo "Please install Ansible to install testing dependencies"; exit 1 )
	@ansible-playbook $(ANSIBLE_BECOME_FLAG) -i "localhost," -c local misc/install-test-dependencies.yml

test:
	@echo "*** Running unittests ***"
	@status=0; \
	$(MAKE) gui-test || status=1; \
	$(MAKE) utils-test || status=1; \
	exit $$status

gui-test:
	@echo "*** Running GUI tests ***"
	PYTHONPATH=.:tests/ xvfb-run -s '-screen 0 640x480x8 -extension RANDR' $(PYTHON) tests/run_tests.py blivetgui_tests

utils-test:
	@echo "*** Running Utils tests ***"
	PYTHONPATH=.:tests/ $(PYTHON) tests/run_tests.py blivetutils_tests

pylint:
	@echo "*** Running pylint ***"
	PYTHONPATH=. tests/pylint/runpylint.py

pep8:
	@echo "*** Running pep8 compliance check ***"
	@if test `which pycodestyle-3` ; then \
		pep8='pycodestyle-3' ; \
	elif test `which pycodestyle` ; then \
		pep8='pycodestyle' ; \
	elif test `which pep8` ; then \
		pep8='pep8' ; \
	else \
		echo "You need to install pycodestyle/pep8 to run this check."; exit 1; \
	fi ; \
	$$pep8 --ignore=E501,E402,E731,W504 blivetgui/ tests/ blivet-gui blivet-gui-daemon

canary:
	$(MAKE) -C po potfile
	PYTHONPATH=translation-canary:$(PYTHONPATH) python3 -m translation_canary.translatable po/blivet-gui.pot

check:
	@status=0; \
	$(MAKE) pylint || status=1; \
	$(MAKE) pep8 || status=1; \
	$(MAKE) canary || status=1; \
	exit $$status

clean:
	-rm blivetgui/*.pyc blivetgui/*/*.pyc ChangeLog
	$(MAKE) -C po clean
	$(PYTHON) setup.py -q clean --all

install:
	$(PYTHON) -m pip install . --root=$(DESTDIR) --verbose --no-deps --no-build-isolation
	$(MAKE) -C po install

ChangeLog:
	(GIT_DIR=.git git log > .changelog.tmp && mv .changelog.tmp ChangeLog; rm -f .changelog.tmp) || (touch ChangeLog; echo 'git directory not found: installing possibly empty changelog.' >&2)

tag:
	tag='$(RELEASE_TAG)' ; \
	git tag -a -s -m "Tag as $$tag" -f $$tag && \
	echo "Tagged as $$tag"

release: tag archive

archive:
	$(MAKE) -B ChangeLog
	git archive --format=tar --prefix=$(APPNAME)-$(VERSION)/ $(RELEASE_TAG) | tar -xf -
	cp -r po $(APPNAME)-$(VERSION)
	cp ChangeLog $(APPNAME)-$(VERSION)/
	( cd $(APPNAME)-$(VERSION) && $(PYTHON) -m build --sdist --outdir .. --no-isolation  )
	rm -rf $(APPNAME)-$(VERSION)
	git checkout -- po/$(APPNAME).pot
	@echo "The archive is in $(APPNAME)-$(VERSION).tar.gz"

local:
	@make -B ChangeLog
	$(PYTHON) -m build --sdist --outdir . --no-isolation
	@echo "The archive is in $(APPNAME)-$(VERSION).tar.gz"

bumpver:
	@NEWSUBVER=$$((`echo $(VERSION) |cut -d . -f 3` + 1)) ; \
	NEWVERSION=`echo $(VERSION).$$NEWSUBVER |cut -d . -f 1,2,4` ; \
	DATELINE="* `LANG="en_US" date "+%a %b %d %Y"` `git config user.name` <`git config user.email`> - $$NEWVERSION-1"  ; \
	cl=`grep -n %changelog blivet-gui.spec | head -1 |cut -d : -f 1` ; \
	tail --lines=+$$(($$cl + 1)) blivet-gui.spec > speclog ; \
	(head -n $$cl blivet-gui.spec ; echo "$$DATELINE" ; make --quiet rpmlog 2>/dev/null ; echo ""; cat speclog) > blivet-gui.spec.new ; \
	mv blivet-gui.spec.new blivet-gui.spec ; rm -f speclog ; \
	sed -i "s/Version: $(VERSION)/Version: $$NEWVERSION/" blivet-gui.spec ; \
	sed -i "s/version='$(VERSION)'/version='$$NEWVERSION'/" setup.py ; \
	sed -i "s/__version__\ =\ '$(VERSION)'/__version__\ =\ '$$NEWVERSION'/" blivetgui/__init__.py ; \
	sed -i "s/version\ =\ '$(VERSION)'/version\ =\ '$$NEWVERSION'/" doc/conf.py ; \
	$(MAKE) potfile

rpmlog:
	@git log --no-merges --pretty="format:- %s (%ae)" $(RELEASE_TAG).. |sed -e 's/@.*)/)/'
	@echo

srpm: local
	rpmbuild -bs --nodeps $(APPNAME).spec --define "_sourcedir `pwd`"
	rm -f $(APPNAME)-$(VERSION).tar.gz

rpm: local
	rpmbuild -bb --nodeps $(APPNAME).spec --define "_sourcedir `pwd`"
	rm -f $(APPNAME)-$(VERSION).tar.gz

deb:
	scripts/build_deb.sh

ci: check test

.PHONY: check pep8 pylint clean install tag archive local deb
