year=$1
first=`ls -d ${year}*.log | head -n 1`
for f in `ls -d ${year}*`;
do if [[ $f > $first ]]
     then
        mv $f TRASH;
     fi 
done
