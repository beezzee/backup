import argparse
import logging
import platform
import os
import os.path
import pathlib
import functools
import subprocess
import datetime
import sys
import re
import tempfile
import shutil

import tabulate

import yaml



logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

datestring = "%Y-%m-%d_%H-%M-%S"

#set PATH=%PATH%;C:\Users\peter.guenther\Documents\workspaces\HardLink\Hardlink\bin\Release
#python3 backup.py --sources C:\Users\peter.guenther\Documents\thesis_new --destination h:\backup\laptop --dry-run


class Configuration(object):
    """Manage configuration.

    Merges options from command line and configuration file.
    """

    def __init__(self):
        self.sources = []
        self.destination = None
        self.file_system = None
        self.parser = None
        self.config_file = None
        self.filter_file = None
        self.func = None

    def __str__(self):
        return str( vars(self))
            
            
    def _add_arguments(self):
        """Add arguments to argument parser.

        """
        
        #no mandatory arguments, because arguments may be read form file
        #the argument names need to match the arguments of this class
        parser.add_argument('--dry-run',action='store_true')
        parser.add_argument('--file-system')
        parser.add_argument('--sources',nargs='*',required=False,type=str)
        parser.add_argument('--destination',type=str)
        parser.add_argument('--config-file','-c',help="Path to YAML configuration")
        parser.add_argument('--filter-file','-f',help="Filter file")
        

    def _parse_args(self):
        if parser is None:
            return
        
        args = parser.parse_args()

        #convert arguments into dictionary
        argsconfig = vars(args)
        fileconfig = dict()
        if args.config_file:
            self.set_file(args.config_file)

        if self.config_file is not None:
            fileconfig = self._parse_file()
            logger.debug(f"Configuration from file {fileconfig}")
        #merge configurations, precedence from command line
        config = fileconfig.copy()

        logger.debug(f"Configuration from command line {argsconfig}")

        #argparse sets non presen arguments to None, filter them out
        #and update the remaining arguments 
        config.update(filter(lambda x: x[1] is not None, argsconfig.items()))

        #apply arguments
        for k,v in config.items():
            logger.debug(f"set {k} to {v}")
            setattr(self, k, v)
            
        self.func = args.func

    def _parse_file(self):
        logger.info(f"Parse configuration file {self.config_file}")
        config = dict()
        with open(self.config_file,'r') as fd:
            config = yaml.safe_load(fd)

        return config

        
    def set_parser(self,parser):
        self.parser = parser
        self._add_arguments()

    def set_file(self,path):
        self.config_file = path
        
    def evaluate(self):
        self._parse_args()
        
    def execute(self):
        self.func(self)
        
def __time_from_pathname__(path):
    #get the name of the directory
    fbase = os.path.basename(path)
    try:
        #try to parse the dirname as date
        astime =  datetime.datetime.strptime(fbase,datestring)
        return astime
    except ValueError:
        return None

def __time_from_filestats__(path):
    stats = os.stat(path)
    creation_time = os.path.getctime(path)

    date = datetime.datetime.fromtimestamp(creation_time)
    return date
    
def is_backup(path):
    if os.path.isdir(path):
        if __time_from_pathname__(path) is not None:
            return True

    return False

def is_tmp(path):
    root,ext = os.path.splitext(path)
    return ext == ".tmp" and is_backup(root)

def tabulate_backups(backup_list):
    headers = ["Directory","Creation Time","Delta"]
    rows = []
    last_time = datetime.datetime.fromtimestamp(0)
    for b in backup_list:
        rows += [(b.date.strftime(datestring),
                  b.ctime().strftime(datestring),
                  str(b.date-last_time))]
        last_time = b.date
    return tabulate.tabulate(rows,headers=headers)
    


@functools.total_ordering
class Backup:
    TMP_EXT=".tmp"
    def __init__(self,destbase,date):
        datedir = date.strftime(datestring)
        self.path = pathlib.Path(destbase,datedir)
        self.date = date

    def __str__(self):
        return f"Backup from {self.date} @ {self.path}"

    def __lt__(self,other):
        return self.date <= other.date

    def __eq__(self,other):
        return self.date == other.date and self.path == other.path

    @property
    def tmp_path(self):
        return self.path.with_suffix(Backup.TMP_EXT)
    
    def ctime(self):
        """Return ctime of this backup.

        On windows, this is the creation time. 
        On Unix, it is the time the directory metadata was modified.
        """
        return __time_from_filestats__(self.path)

    def commit(self):
        d=self.path
        p=pathlib.Path(self.tmp_path)
        if d.exists():
            raise FileExistsError(f"Destination path {d} exists")
        p.rename(d)
        

    @classmethod
    def from_path(cls,path):
        date_from_path = __time_from_pathname__(path.name)
        # date_from_filestats = __time_from_filestats__(path)
        # if abs(date_from_path-date_from_filestats)>datetime.timedelta(seconds=1):
        #     logger.warn(f"Discrepancy between creation time of directory ({date_from_filestats}) and directory name ({date_from_path})")
        #     logger.warn("Take date from pathname")
        return cls(path.parent,date_from_path)


def unify_path(path,drive_prefix='\cygdrive'):
    drive,subpath = os.path.splitdrive(path)
    if drive == "":
        logger.debug(f"Path {path} does not contain drive.")
        return path
    else: 
        match = re.match('\s*(?P<drive>\w):',drive)
        if match:
            drive = match.group('drive')
            logger.debug(f"Identified drive {drive}")
            replacement  = os.path.join(drive_prefix, drive + subpath)

            logger.warning(f"Replace path {path} with {replacement}")
            return replacement
        else:
            logger.error(f"Not a valid drive: {drive}")
            return path


def execute_system_command(cmd):
    string = ""
    for e in cmd:
        string += e + " " 

    logger.info(f"Execute {string}")


    #completed_process  = subprocess.run(cmd,check=False,shell=False,capture_output=True)
    completed_process  = subprocess.run(cmd,check=False,shell=False)

    try:
        completed_process.check_returncode()
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occured during execution of {e.cmd}")
        logger.error(f"Returncode: {e.returncode}")
        logger.error(f"Output: {e.output}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")

    return completed_process
    

def compile_rsync_command(src,dest,target_fst,dry_run=True,logfile=None,link_dest=None,thorough_check=False,filter_file=None):
    cmd=["rsync"]
    rsync_filters = []
    #['--exclude=lost+found', '--exclude=.cache/']

    rsync_options = ["--ignore-existing","--hard-links","--sparse"]

    #--delete is not required, because destination should be empty
    #rsync_options += ["--delete"]

    #print progress information and statistics
    rsync_options += ["--info=stats2,progress2"]

    if target_fst == "NTFS":
        #emulate --archive, but without --perms --owner --group
        
        #rsync_options += ["--no-perms", "--no-owner", "--no-group"]
        rsync_options += ["--times"]

        #preserve device and special files
        rsync_options += ["-D"]
        
        #copy directories recursively
        rsync_options += ['--recursive']
        
        #copy symlinks as symlinks
        rsync_options += ['--links']
    else:
        rsync_options += ["--archive"]


    for o in rsync_options+rsync_filters:
        cmd+= [o] 
        
    if logfile is not None:
        cmd+= ["--log-file=" + logfile]

    if dry_run:
        cmd += ["--dry-run"]

    if link_dest is not None:            
        cmd+= ["--link-dest=" + link_dest ]

    if thorough_check:
        cmd += ["--checksum"]

    if filter_file is not None:
        #include filter file via merge rule, convert to absolute path
        cmd += ["--filter=merge " + str(pathlib.Path(filter_file).resolve())]
        
    cmd+= [src]

    #second positional argument of rsycn: dest
    #backup_path_unified = unify_path(backup.path)
    cmd+= [dest]
    return cmd

def compile_hardlink_command(src,dest,target_fst,dry_run=True,logfile=None,link_dest=None,thorough_check=False):
    cmd =[]

    if dry_run:
        cmd+=["echo"]

    cmd += ["HardLink"]

    cmd += [f"--source-folder", src]
    cmd += [f"--destination",dest]
    if link_dest is not None:
        cmd += [f"--link-dest",link_dest]
    cmd += [f"--logfile",logfile]

    return cmd

#compile_backup_command=compile_hardlink_command
compile_backup_command=compile_rsync_command


def yield_backups(destbase):
    if destbase is None or not os.path.isdir(destbase):
        logging.error(f"The destination directory {destbase} does not exist or is not a directory.")   
        raise ValueError from None
        
    for f in os.listdir(destbase):
        fpath = os.path.join(destbase,f)
        if os.path.isdir(fpath):
            fbase = os.path.basename(fpath)
            logger.debug(f"Found directory {fbase} in backup destination.")
            if is_backup(fpath):
                logger.debug(f"Accept as backup")
                yield Backup.from_path(pathlib.Path(fpath))

def list_backups(config):
    logger.debug(f"List backups in {config.destination}.")
    print(tabulate_backups(sorted(yield_backups(config.destination))))

def backup(config):
    source_dirs = config.sources
    target_fst = config.file_system
    destbase = config.destination

    hostname=platform.node()

    now = datetime.datetime.now()

    logger.debug(f"Destination backup directory {destbase}")
      

    backup = Backup(destbase,now)
    logging.debug(f"Destination directory {backup.path}")
    existing_backups = list(yield_backups(destbase))
    
    existing_backups.sort()
    logging.info(f"Found {len(existing_backups)} backups.")
    for b in existing_backups:
        logger.debug(str(b))

    if existing_backups:
        last_backup= existing_backups[-1]
        logging.info(f"Last backup was {last_backup}")
        first_backup_of_month = last_backup.date.month != now.month or last_backup.date.year != now.year
    else:
        logger.info("No backups existing yet.")
        last_backup = None
        first_backup_of_month = True
        
    #logfile = os.path.normpath(backup.path) + ".log"
    logfile = str(backup.path.with_suffix(".log"))
    logger.info(f"Log to {logfile}")

    if last_backup is not None:
        #link_dest = os.path.normpath(last_backup.path + '/')
        #link_dest = os.path.normpath(last_backup.path)
        link_dest = last_backup.path
        if not link_dest.is_absolute():
            #we searched for existing backups in destination directory
            #rsync handles relative path as relative path to destination directory
            link_dest = pathlib.Path("..") / link_dest.name

        logger.info(f"Create backup at {backup} relative to {last_backup}.")
    else:
        link_dest = None
 
    #tmpdest = tempfile.mkdtemp(dir=destbase)
    #tmpdest = os.path.join(destbase , 'tmpdir')
    #os.mkdir(tmpdest)

    #logger.info(f"Temporary backup destination {tmpdest}")

    backup_errors=0
    for src_dir in source_dirs:
        if os.path.isdir(src_dir):
            logging.info(f"Backup {src_dir}...")

            
            #we already know that src_dir is a directory, hence normpath will remove potential trailing slashes 
            
            #first positional argument of rsync: src
            src_dir_normalized = os.path.normpath(src_dir) 
            #src_dir_unified = unify_path(src_dir_normalized)

            src_head,src_tail = os.path.split(src_dir_normalized)
            if src_tail == '':
                #if there was a trailing slash in the path name
                src_head,src_tail = os.path.split(src_head)
            

            #dest = tmpdest
            dest = str(backup.tmp_path)
            src = os.path.join(src_head,src_tail)
            if link_dest is None:
                link_dest_dir = None
            else:
                link_dest_dir = str(link_dest)
                #link dest needs to be parent of src_dir that we currently process
                #otherwise linking does not work
                #link_dest_dir = os.path.join(link_dest,src_tail)

            cmd=compile_backup_command(target_fst=config.file_system,dry_run=config.dry_run,logfile=logfile,src=src,dest=dest,link_dest=link_dest_dir,thorough_check=first_backup_of_month,filter_file=config.filter_file)

            if errors>0:
                logger.info("Skip rsync because errors happened.")
            # elif args.dry_run:
            #     logger.info("Skip rsync for dry run")
            else:
                completed_process = execute_system_command(cmd)
                if completed_process.returncode != 0:
                    backup_errors+=1
                    logger.error(f"Error during execution of {cmd[0]}.")

                
        else: 
            logging.warning(f"{src_dir} is not a directory. Skip for backup.")


    if backup_errors>0:
        logger.error(f"Errors during backup.")
        if not config.dry_run:
            logger.error(f"Manually inspect {backup.tmp_path} and remove manually (rm -r {backup.tmp_path})")
    else:
        logger.info(f"Backup successful.")
        if not config.dry_run:
            logger.info(f"Move result to final destination {backup.path}")
            backup.commit()
            
    # elif not args.dry_run:
    #     logger.debug(f"Move temporary directory {tmpdest} to {backup.path}")
    #     try:
    #         os.rename(tmpdest,backup.path)
    #     except OSError as e:
    #         logger.error(f"Renaming failed with {e}")
    # else:
    #     logger.info(f"Remove temporary directory {tmpdest}")
    #     try:
    #         shutil.rmtree(tmpdest)            
    #     except:
    #         logger.error(f"Error during removal of {tmpdest}. Remove manually.")
        
  

if __name__ == "__main__":
    errors = 0

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)
    parser_list = subparsers.add_parser('list-backups')
    parser_list.set_defaults(func=list_backups)
    
    parser_backup = subparsers.add_parser('backup')
    parser_backup.set_defaults(func=backup)
    
    config = Configuration()

    config.set_parser(parser)

    # evaluate arguments and implicitly read configuation field
    config.evaluate()

    logger.debug(f"Configuration {config}")
    
    config.execute()
    


