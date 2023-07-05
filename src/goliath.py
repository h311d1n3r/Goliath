import argparse
import logging
import subprocess
import os
import sys
import requests
import tarfile
from log import LogFormatter
from shutil import which

def init_logging():
    fmt = LogFormatter()
    hdlr = logging.StreamHandler(sys.stdout)
    hdlr.setFormatter(fmt)
    logging.root.addHandler(hdlr)
    logging.root.setLevel(logging.INFO)

def download_and_extract_version(version):
    logging.info('Downloading Go v'+version+'...')
    response = requests.get('https://go.dev/dl/go'+version+'.src.tar.gz')
    dl_dir = os.getcwd()+'/go-'+version
    os.makedirs(dl_dir, exist_ok=True)
    with open(dl_dir+'/go.tar.gz', "wb") as tar_file:
        tar_file.write(response.content)
        tar_file.close()
    logging.info('Extracting Go v'+version+'...')
    with tarfile.open(dl_dir+'/go.tar.gz', "r:gz") as tar:
        tar.extractall(dl_dir)
        tar.close()
    os.remove(dl_dir+'/go.tar.gz')
    return True

def patch(version):
    logging.info('Applying patch...')
    work_dir = os.getcwd()+'/go-'+version+'/go'
    sub_version = version[version.index('.')+1:]
    if '.' in sub_version:
        sub_version = sub_version[:sub_version.index('.')]
    sub_version = int(sub_version, 10)
    if sub_version < 15:
        logging.fatal('Goliath currently handles versions >= 1.15')
        return False
    loader_f = open(work_dir+'/src/cmd/link/internal/loader/loader.go', 'r')
    lines = loader_f.read()
    loader_f.close()
    loader_f = open(work_dir+'/src/cmd/link/internal/loader/loader.go', 'w')
    for line in lines.split('\n'):
        if 'func NewLoader(' in line:
            loader_f.write('func (l *Loader) GetSymsByName() [2]map[string]Sym {\n')
            loader_f.write('\treturn l.symsByName\n')
            loader_f.write('}\n\n')
        loader_f.write(line+'\n')
    loader_f.close()
    deadcode_f = open(work_dir+'/src/cmd/link/internal/ld/deadcode.go', 'r')
    lines = deadcode_f.read()
    deadcode_f.close()
    deadcode_f = open(work_dir+'/src/cmd/link/internal/ld/deadcode.go', 'w')
    for line in lines.split('\n'):
        if 'for _, name := range names {' in line:
            deadcode_f.write('\tvar symNames = (*d.ldr).GetSymsByName()[1]\n')
            deadcode_f.write('\tfor symName := range symNames {\n')
            deadcode_f.write('\t\tnames = append(names, symName)\n')
            deadcode_f.write('\t}\n\n')
        deadcode_f.write(line+'\n')
    deadcode_f.close()
    return True

def build(version):
    logging.info('Building Go...')
    work_dir = os.getcwd()+'/go-'+version+'/go'
    build_output = subprocess.run(['./make.bash'], cwd=work_dir+'/src', capture_output=True)
    if not b'Installed Go for' in build_output.stdout:
        logging.fatal('Error !')
        logging.fatal(build_output.stderr.decode())
        return False
    return True

if __name__ == '__main__':
    init_logging()
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('version', nargs='?', type=str)
    args = parser.parse_args()
    if not args.version:
        logging.fatal('Syntax: goliath version')
        sys.exit(1)
    goroot = os.getenv('GOROOT')
    if goroot is None:
        logging.fatal('Environment variable GOROOT is not set. Please install and setup go correctly then retry.')
        sys.exit(1)
    if not download_and_extract_version(args.version):
        sys.exit(1)
    if not patch(args.version):
        sys.exit(1)
    if not build(args.version):
        sys.exit(1)
    logging.success('Done !')
