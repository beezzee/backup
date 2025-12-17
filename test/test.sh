touch src/dir1/updated_file
python3 ../backup.py -c test.yaml backup
echo "Manually check that inodes of fixed_file are fixed between runs"
find -printf "%p %i\n"
