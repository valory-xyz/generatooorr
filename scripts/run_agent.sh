rm -r agent
find packages/ -empty -type d -delete  # remove empty directories to avoid wrong hashes
autonomy packages lock
autonomy fetch --local --agent valory/generatooorr --alias agent && cd agent
autonomy generate-key ethereum
autonomy add-key ethereum ethereum_private_key.txt
autonomy issue-certificates
