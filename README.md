# Backup 

## Introduction

This is yet another backup tool. Although, it is more a backup strategy than a tool. The strategy is supported by standard unix tools and consists of three major parts

1. Generation of backups
2. Management of backups
3. Recovery of backups

This document introduces strategies how to accomplish all three tasks with standard tools like `rsync`, `find`, and `cp`. This provides flexibility and means for automation. 

The backups we generate are *synthetic backups*, i.e., the generation of the backup is incremental, but such that always a full backup is provided for recovery. We do this based on file system hard links:
1. If a file changed since the last backup, it will be copied to the backup.
2. If a file did not changed since the last backup, it will be hard linked to the previous backup.

We let `rsync --link-dest` do this job.

## Glossary and Definitions

* *Backup sequence:* A sequence starting with a full backup and subsequent incremental backups.

## Generating Backups

To generate a backup, we use the `rsync` tool. We provide a wrapper
scrip for `rsync` that manages search for the last backup, naming of
new backups, and compiling the `rsync` command with the required
parameters.

### Filtering source folders

To filter the backup source folder, we include a filter file provided
by the `--filter-file` option. This file is passed to the `rsync`
`--filter` option through the rsync `merge` filter rule. For more
background, see the `rsync` man page, section `FILTER RULES`.

The following filter file shows a very basic example, that includes
the `/var`, `/etc`, `/root`, `/home/foo` folders, relative to the
backup source folders (provided via the `--source`) option.  It
excludes the contents of `.cache` folders under home directories and
`/var/cache`.

```
+ /var/
- /var/cache/*
+ /etc/
+ /root/
+ /home/
+ /home/foo/
- /home/*/.cache/*
- /home/*
- /*
```

Note: because filters are applied from root downwards, a directory
up in the tree has to be explicitly included before it is excluded by
subsequent filters. For example, we explicitly include the `/home`
folder to be able to include the `/home/foo` folder. Otherwise, the
`/*` filter would exclude the `/home` folder and hence, also
`/home/foo` would be excluded as subfolder of `/home`. By adding
`/home` before the `/*` exclude rule, the `/home` include rule takes
precedence over excluding it through `/*`.  The `/home/*` exclude rule
is for excluding all home folders except the explicitly included
`/home/foo` folder.

For more complex include and exclude patterns, for example
per-directory filters, refer to the `FILTER RULES` section of the
`rsync` man page.

## Managing Backups

### Collapsing differential backups

To collapse all backups of 2017 to the first backup of this year, do

```
year=2017
mkdir TRASH
first=`ls -d ${year}*.log | head -n 1`
for f in `ls -d ${year}*`;
  do if [[ $f > $first ]]
     then
    	mv $f TRASH;
     fi	
  done
```

### Branching off a new sequence

Next we describe how to start a new differential backup relative to a snapshot `base` of
a given differential backup `current_sequence`, i.e., `base` is a subdirectory of `currrent_sequence`. 

Suppose there is a sequence of differential backups in `current_sequence` with a snapshot `base` and we like to branch of a new sequence into `new_sequence`. We use

```
BASE=current_sequence/base
NEW=new_sequence

cp --archive --link $BASE $NEW
```
1. The `--archive` option ensures that symbolic links and file attributes are preserved.
2. The `--link` lets `cp` generate hard links to base.

TODO: I think the `--archive` option is not required, because hard links should preserve attributes anyhow.

By using hard links we have the advantage that no new files are created and hence no additional space is required. Furthermore the operation is much faster. 

If eventually, `$BASE` is removed, the files still exist in `$NEW/base`. 

## Recovering Backups

### Searching for snapshots of file

```
find <backup_dir> -path etc/environment 
```

### Searching for file with same inode

```
find <backup_dir> -samefile <reference_file>
```

## Securing Backups

In this section, we discuss how to secure a backup. The main goal is to prevent modification of backups from a potentially corrupted system. We implement the following measures:

1. The backup system has read-only access to the source system.
2. The source system has no access to the backup storage.

The first property reduces access rights of the backup to the requried minimum. The second property is important to prevent that a corrupted system modifies or destroys its backups. The rationale is that the source system might be corrupted but the backup system is clean. This is a reasonable assumption because:

1. The source system is usually a complex system that, at some point in time, might be under control of the attacker. E.g., a ransomware on the source system will try to encrypt or destroy backups. Actually, the potential corruption of the source system is the major reason for backups. 
2. The backup system has only a limited functionality, i.e., performing the backup. Hence, it is much simpler to guarantee its integrity.

### Access to source files from backup system

1. Same system, different users. Backup user has read only access to source.
2. Different system. Backup system mounts source read only. Source permits only read-only mount.
3. Different system. Backup system accesses source through ssh. Authentication, e.g, with ssh key.

### Access to backup storage from backup system

1. Local, mounted read-write
2. Remote, mounted read-write
3. Remote, through ssh