#!/usr/bin/env python3
"""Enable Dropbear and add a password-login service user to an extracted IDEC OS.

From scratch/:
    ./setup_hmi_dropbear.py Mod_Read_regs/os_update --hash-file service.hash

Patches the extracted directory and rebuilds the sibling os_update.tar.xz.
Original tar metadata is retained, except for explicitly added/changed entries.
No service .ssh directory or authorized_keys are created.
"""

import argparse
import copy
import io
import os
import re
import tarfile
from pathlib import Path

UID = 1001
GID = 1001


def norm(name):
    return name.removeprefix('./').rstrip('/')


def update_entry(data, user, entry):
    lines = data.decode('utf-8').splitlines()
    indices = [i for i, line in enumerate(lines) if line.split(':', 1)[0] == user]
    if len(indices) > 1:
        raise ValueError(f'Duplicate {user} account entries')
    if indices:
        lines[indices[0]] = entry
    else:
        lines.append(entry)
    return ('\n'.join(lines) + '\n').encode()


def dropbear_config(data):
    keys = {'DROPBEAR_EXTRA_ARGS': '""', 'DROPBEAR_PORT': '22', 'NO_START': '0'}
    lines = []
    for line in data.decode('utf-8').splitlines():
        key = line.split('=', 1)[0].strip() if '=' in line else ''
        if not line.lstrip().startswith('#') and key in keys:
            continue
        lines.append(line)
    lines.extend(f'{key}={value}' for key, value in keys.items())
    return ('\n'.join(lines) + '\n').encode()


def entry(name, mode, uid=0, gid=0, kind=tarfile.REGTYPE, link=''):
    info = tarfile.TarInfo('./' + name)
    info.type, info.mode, info.uid, info.gid = kind, mode, uid, gid
    info.uname = info.gname = ''
    info.linkname = link
    return info


def apply(root, hash_file, host_key):
    if not root.is_dir():
        raise ValueError(f'Extracted OS directory not found: {root}')
    archive = root.parent / 'os_update.tar.xz'
    if not archive.is_file():
        raise ValueError(f'Expected adjacent archive: {archive}')
    password_hash = hash_file.read_text().strip()
    if not re.fullmatch(r'\$6\$[^:\s]+\$[^:\s]+', password_hash):
        raise ValueError('Hash file must contain a SHA-512 crypt hash ($6$...)')

    with tarfile.open(archive, 'r:xz') as original:
        members = original.getmembers()
        sources = {norm(m.name): m for m in members}
        if len(sources) != len(members):
            raise ValueError('Duplicate normalized names in archive')
        necessary = ('etc/passwd', 'etc/group', 'etc/shadow',
                     'etc/default/dropbear', 'etc/init.d/dropbear')
        if any(name not in sources for name in necessary):
            raise ValueError('Archive missing one of: ' + ', '.join(necessary))

        patched = {}
        fields = {
            'etc/passwd': 'service:x:1001:1001:Service SSH:/home/service:/bin/sh',
            'etc/group': 'service:x:1001:',
            'etc/shadow': f'service:{password_hash}:20736:0:99999:7:::',
        }
        for name, value in fields.items():
            patched[name] = update_entry(original.extractfile(sources[name]).read(),
                                         'service', value)
        patched['etc/default/dropbear'] = dropbear_config(
            original.extractfile(sources['etc/default/dropbear']).read())

        if host_key is not None:
            patched['etc/dropbear/dropbear_rsa_host_key'] = host_key.read_bytes()

        additions = {}
        if 'home/service' not in sources:
            additions['home/service'] = entry('home/service', 0o700, UID, GID,
                                              tarfile.DIRTYPE)
        if 'etc/rc5.d/S20dropbear' not in sources:
            additions['etc/rc5.d/S20dropbear'] = entry(
                'etc/rc5.d/S20dropbear', 0o777, kind=tarfile.SYMTYPE,
                link='../init.d/dropbear')

        temp = archive.with_name(archive.name + '.partial')
        try:
            with tarfile.open(temp, 'w:xz', format=original.format) as dest:
                for member in members:
                    name = norm(member.name)
                    meta = copy.copy(member)
                    if name == 'home/service':
                        meta.uid, meta.gid, meta.mode = UID, GID, 0o700
                    if name == 'etc/rc5.d/S20dropbear':
                        meta.type = tarfile.SYMTYPE
                        meta.linkname = '../init.d/dropbear'
                        meta.size = 0
                    if name in patched:
                        content = patched[name]
                        meta.size = len(content)
                        if name == 'etc/shadow':
                            meta.mode = 0o600
                        if name == 'etc/dropbear/dropbear_rsa_host_key':
                            meta.uid = meta.gid = 0
                            meta.mode = 0o600
                        dest.addfile(meta, io.BytesIO(content))
                    else:
                        dest.addfile(meta, original.extractfile(member) if member.isfile()
                                     and name != 'etc/rc5.d/S20dropbear' else None)
                for name, meta in additions.items():
                    dest.addfile(meta)
                if 'etc/dropbear/dropbear_rsa_host_key' in patched and \
                        'etc/dropbear/dropbear_rsa_host_key' not in sources:
                    content = patched['etc/dropbear/dropbear_rsa_host_key']
                    meta = entry('etc/dropbear/dropbear_rsa_host_key', 0o600)
                    meta.size = len(content)
                    dest.addfile(meta, io.BytesIO(content))

            with tarfile.open(temp, 'r:xz') as test:
                result = {norm(m.name): m for m in test}
                for name in (*necessary, 'home/service', 'etc/rc5.d/S20dropbear'):
                    if name not in result:
                        raise ValueError(f'Archive verification failed: {name}')
                if result['home/service'].uid != UID or result['home/service'].gid != GID:
                    raise ValueError('Wrong service account ownership in tar archive')
                if result['etc/rc5.d/S20dropbear'].linkname != '../init.d/dropbear':
                    raise ValueError('Wrong Dropbear startup symlink')

            # Keep extracted worktree in sync with the newly produced tar archive.
            for name, content in patched.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                if name in ('etc/shadow', 'etc/dropbear/dropbear_rsa_host_key'):
                    path.chmod(0o600)
            service_home = root / 'home/service'
            service_home.mkdir(parents=True, exist_ok=True)
            service_home.chmod(0o700)
            link = root / 'etc/rc5.d/S20dropbear'
            link.parent.mkdir(parents=True, exist_ok=True)
            if link.is_symlink() and os.readlink(link) != '../init.d/dropbear':
                raise ValueError('Existing S20dropbear link points somewhere else')
            if not link.exists() and not link.is_symlink():
                link.symlink_to('../init.d/dropbear')

            os.replace(temp, archive)
        finally:
            temp.unlink(missing_ok=True)

    print(f'Updated extracted OS: {root}')
    print(f'Rebuilt OS archive:  {archive}')
    print('Dropbear: port 22, runlevel 5 startup, password login enabled')
    print('service: UID/GID 1001, password hash configured')
    print('No service .ssh directory or authorized_keys created')
    print('Tar ownership: original member metadata preserved; service home = 1001:1001')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Extracted os_update directory')
    parser.add_argument('--hash-file', type=Path, required=True)
    parser.add_argument('--host-key', type=Path,
                        help='Optional existing unique RSA Dropbear host key')
    args = parser.parse_args()
    apply(args.directory, args.hash_file, args.host_key)


if __name__ == '__main__':
    main()
