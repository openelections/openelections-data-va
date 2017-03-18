import argparse
import csv
import re
import sys

arg_parser = argparse.ArgumentParser(description='Parse nyc voting csv\'s.')
arg_parser.add_argument('csvfilepath', type=str, nargs=1)
arg_parser.add_argument('--print_header', type=bool, default=False)
arg_parser.add_argument('--office', type=str, required=True)
arg_parser.add_argument('--district', type=str, default='')

args = arg_parser.parse_args()

if args.print_header:
  print('county,precinct,office,district,party,candidate,votes,other_votes,blank_votes,total_votes')

candidates = []
parties = []
with open(args.csvfilepath[0], 'rb') as csvfile:
  line = csv.reader(csvfile, delimiter=',', quotechar='"')
  line_number = 0
  for row in line:
    if line_number == 0:
      index = 3
      while index < len(row) - 3:
        candidates.append(row[index])
        index += 1
      line_number += 1
      continue
    if line_number == 1:
      index = 3
      while index < len(row):
        parties.append(row[index])
        index += 1
      line_number += 1
      continue
    county = row[0]
    if county == 'TOTALS':
      continue
    ward = row[1]
    precinct = row[2]
    total_votes = int(row[len(row) - 1].replace(',',''))
    blank_votes = int(row[len(row) - 2].replace(',',''))
    other_votes = int(row[len(row) - 3].replace(',',''))
    index = 3
    candidate_votes = []
    while index < len(row) - 3:
      candidate_votes.append(int(row[index].replace(',','')))
      index += 1
    for idx,votes in enumerate(candidate_votes):
      print '%s,%s,%s,%s,%s,%s,%d,%d,%d,%d' % (
        county, precinct, args.office, args.district, parties[idx],
        candidates[idx], votes, other_votes, blank_votes, total_votes)
    line_number += 1
