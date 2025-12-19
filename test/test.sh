touch src/dir1/updated_file
python ../backup.py -c test.yaml backup
python ../backup.py -c test.yaml list-backups
echo "Manually check that inodes of fixed_file are fixed between runs"
find -printf "%p %i\n"
