import csv
import re
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'Data'
OUT_DIR = DATA_DIR / 'openelections'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def clean_name(value: str) -> str:
    return (value or '').strip().strip('"').replace('  ', ' ')


def parse_office_and_district(office_title: str, district_name: str) -> tuple[str, str]:
    office_title = clean_name(office_title)
    district_name = clean_name(district_name)

    m = re.match(r'^(.*)\s*\(([^()]*)\)\s*$', office_title)
    if m:
        base_office = clean_name(m.group(1))
        parsed_district = clean_name(m.group(2))
    else:
        base_office = office_title
        parsed_district = ''

    district = parsed_district or district_name
    if district.lower() in {'virginia', 'state', 'commonwealth of virginia'}:
        district = ''

    return base_office, district


def normalize_votes(v) -> str:
    if v is None:
        return ''
    s = str(v).strip().replace(',', '')
    if s == '':
        return ''
    return str(int(float(s)))


def election_day_november(year: int) -> str:
    d = date(year, 11, 1)
    while d.weekday() != 0:  # Monday
        d += timedelta(days=1)
    d += timedelta(days=1)  # Tuesday after first Monday
    return d.strftime('%Y%m%d')


def office_from_filename(src: Path) -> str:
    stem = src.stem
    m = re.match(r'^Virginia_Elections_Database__\d{4}_(.+?)_General_Election(?:\s+\(\d+\))?$', stem)
    if not m:
        return 'unknown_office'
    office_token = m.group(1).replace('_', ' ').strip().lower()

    mapping = {
        'president': 'president',
        'u s senate': 'us_senate',
        'governor': 'governor',
        'lieutenant governor': 'lieutenant_governor',
        'attorney general': 'attorney_general',
    }
    return mapping.get(office_token, re.sub(r'[^a-z0-9]+', '_', office_token).strip('_'))


def year_from_filename(src: Path) -> int:
    m = re.match(r'^Virginia_Elections_Database__(\d{4})_', src.stem)
    if not m:
        raise ValueError(f'Could not parse year from filename: {src.name}')
    return int(m.group(1))


def convert_2025_precinct_file(src: Path, dst: Path) -> int:
    fieldnames = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes']
    out_rows = 0

    with src.open('r', encoding='utf-8-sig', newline='') as f_in, dst.open('w', encoding='utf-8', newline='') as f_out:
        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            office, district = parse_office_and_district(row.get('OfficeTitle', ''), row.get('DistrictName', ''))
            county = clean_name(row.get('LocalityName', ''))
            precinct = clean_name(row.get('PrecinctName', ''))
            party = clean_name(row.get('Party', ''))
            candidate = clean_name(row.get('CandidateName', ''))
            votes = normalize_votes(row.get('TOTAL_VOTES', ''))

            writer.writerow(
                {
                    'county': county,
                    'precinct': precinct,
                    'office': office,
                    'district': district,
                    'party': party,
                    'candidate': candidate,
                    'votes': votes,
                }
            )
            out_rows += 1

    return out_rows


def convert_county_wide_file(src: Path, dst: Path, office: str) -> int:
    fieldnames = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes']
    out_rows = 0

    with src.open('r', encoding='utf-8-sig', newline='') as f_in, dst.open('w', encoding='utf-8', newline='') as f_out:
        reader = csv.reader(f_in)
        rows = list(reader)

        if len(rows) < 3:
            raise ValueError(f'Unexpected format in {src}')

        header_names = rows[0]
        header_parties = rows[1]

        candidate_cols = []
        for i in range(3, len(header_names)):
            candidate = clean_name(header_names[i])
            if candidate in {'', 'Total Votes Cast'}:
                continue
            party = clean_name(header_parties[i]) if i < len(header_parties) else ''
            if candidate.lower() == 'all others' and not party:
                party = 'Other'
            candidate_cols.append((i, candidate, party))

        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows[2:]:
            if not row:
                continue
            county = clean_name(row[0])
            if not county:
                continue

            for col_idx, candidate, party in candidate_cols:
                if col_idx >= len(row):
                    continue
                votes = normalize_votes(row[col_idx])
                if votes == '':
                    continue

                writer.writerow(
                    {
                        'county': county,
                        'precinct': 'TOTAL',
                        'office': office,
                        'district': '',
                        'party': party,
                        'candidate': candidate,
                        'votes': votes,
                    }
                )
                out_rows += 1

    return out_rows


def main() -> None:
    # Remove existing outputs to avoid stale/duplicate files.
    for p in OUT_DIR.glob('*.csv'):
        p.unlink()

    converted_files = 0
    skipped_duplicates = 0

    src_2025 = DATA_DIR / 'Election Results_Nov_2025.csv'
    if src_2025.exists():
        dst_2025 = OUT_DIR / '20251104__va__general__statewide__precinct.csv'
        c = convert_2025_precinct_file(src_2025, dst_2025)
        print(f'Wrote {dst_2025.name} ({c} rows)')
        converted_files += 1

    seen = set()
    for src in sorted(DATA_DIR.glob('Virginia_Elections_Database__*_General_Election*.csv')):
        year = year_from_filename(src)
        office_slug = office_from_filename(src)
        election_date = election_day_november(year)
        out_name = f'{election_date}__va__general__{office_slug}__county.csv'
        dst = OUT_DIR / out_name

        if out_name in seen:
            skipped_duplicates += 1
            print(f'Skipped duplicate source: {src.name} -> {out_name}')
            continue

        office_label = office_slug.replace('_', ' ').title()
        c = convert_county_wide_file(src, dst, office_label)
        print(f'Wrote {dst.name} ({c} rows)')
        converted_files += 1
        seen.add(out_name)

    print(f'Converted {converted_files} files total. Skipped {skipped_duplicates} duplicate source files.')


if __name__ == '__main__':
    main()
