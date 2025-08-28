#!/usr/bin/env python3
#ProjectGuardian2.0
import csv
import json
import re
import sys
from typing import Dict, List, Set, Tuple, Any


class PIIDetector:
    def __init__(self):
        # Regex patterns for standalone PII detection
        self.patterns = {
            'phone': re.compile(r'\b\d{10}\b'),  # 10-digit numbers
            'aadhar': re.compile(r'\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b'),  # 12-digit starting with 2-9
            'passport': re.compile(r'\b[A-Z]\d{7}\b', re.IGNORECASE),  # Letter followed by 7 digits
            'upi': re.compile(r'\b[a-zA-Z0-9.-]{2,256}@[a-zA-Z]{2,64}\b'),  # UPI format
            'email': re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'),
        }

        # Patterns for detection
        self.phone_variations = [
            re.compile(r'\b\+91[-\s]?[789]\d{9}\b'),  # +91 format
            re.compile(r'\b91[789]\d{9}\b'),          # 91 prefix
            re.compile(r'\b[789]\d{9}\b'),            # Direct 10-digit
        ]

        # Name detection 
        self.name_pattern = re.compile(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b')

    def is_phone_number(self, text: str) -> bool:
        """Check if text contains phone number"""
        if not text:
            return False

        # Convert to string and remove spaces and common separators for checking
        str_text = str(text).strip()
        cleaned = re.sub(r'[-\s()]', '', str_text)

        # Check various phone number patterns
        if self.patterns['phone'].search(cleaned):
            return True

        for pattern in self.phone_variations:
            if pattern.search(str_text):
                return True

        return False

    def is_aadhar_number(self, text: str) -> bool:
        """Check if text contains Aadhar number"""
        if not text:
            return False

        str_text = str(text).strip()

        # Check with and without spaces - but must start with 2-9
        if self.patterns['aadhar'].search(str_text):
            return True

        # Remove spaces and check 12-digit format starting with 2-9
        cleaned = re.sub(r'\s', '', str_text)
        if re.match(r'^[2-9]\d{11}$', cleaned):
            return True

        return False

    def is_passport_number(self, text: str) -> bool:
        """Check if text contains passport number"""
        if not text:
            return False
        return bool(self.patterns['passport'].search(str(text).strip()))

    def is_upi_id(self, text: str) -> bool:
        """Check if text contains UPI ID"""
        if not text:
            return False
        return bool(self.patterns['upi'].search(str(text).strip()))

    def is_email(self, text: str) -> bool:
        """Check if text contains email address"""
        if not text:
            return False
        return bool(self.patterns['email'].search(str(text).strip()))

    def extract_names(self, text: str) -> List[str]:
        """Extract potential names from text"""
        if not text:
            return []

        names = []
        str_text = str(text).strip()
        # Look for capitalized first + last name combinations
        matches = self.name_pattern.findall(str_text)
        for match in matches:
            # Skip common false positives
            words = match.split()
            if len(words) >= 2 and not any(word.lower() in ['new', 'york', 'san', 'los', 'las', 'north', 'south', 'east', 'west'] for word in words):
                names.append(match)
        return names

    def redact_text(self, text: str, entity_type: str) -> str:
        """Redact sensitive information from text"""
        if not text:
            return str(text)

        redacted = str(text).strip()

        if entity_type == 'phone':
            for pattern in self.phone_variations:
                redacted = pattern.sub(lambda m: m.group()[:2] + 'X' * (len(m.group()) - 4) + m.group()[-2:], redacted)
            redacted = self.patterns['phone'].sub(lambda m: m.group()[:2] + 'X' * 6 + m.group()[-2:], redacted)

        elif entity_type == 'aadhar':
            # Improved Aadhar redaction
            def redact_aadhar(match):
                aadhar = match.group()
                # Keep last 4 digits
                if ' ' in aadhar:
                    return 'XXXX XXXX ' + aadhar[-4:]
                else:
                    return 'XXXXXXXX' + aadhar[-4:]
            redacted = self.patterns['aadhar'].sub(redact_aadhar, redacted)

        elif entity_type == 'passport':
            redacted = self.patterns['passport'].sub('[REDACTED_PASSPORT]', redacted)

        elif entity_type == 'upi':
            redacted = self.patterns['upi'].sub(lambda m: m.group().split('@')[0][:3] + 'XXX@' + m.group().split('@')[1], redacted)

        elif entity_type == 'email':
            def redact_email(match):
                email = match.group()
                parts = email.split('@')
                if len(parts[0]) > 3:
                    return parts[0][:3] + 'XXX@' + parts[1]
                else:
                    return 'XXX@' + parts[1]
            redacted = self.patterns['email'].sub(redact_email, redacted)

        elif entity_type == 'name':
            names = self.extract_names(redacted)
            for name in names:
                parts = name.split()
                masked = parts[0][0] + 'XXX ' + parts[-1][0] + 'XXX' if len(parts) >= 2 else 'XXXX'
                redacted = redacted.replace(name, masked)

        return redacted

    def analyze_record(self, data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Analyze a record for PII and return detection status and redacted data"""
        has_pii = False
        redacted_data = {}

        # Track combinatorial PII elements
        combinatorial_elements = {
            'name': [],
            'email': [],
            'address': [],
            'device_id': [],
            'ip_address': []
        }

        for key, value in data.items():
            if value is None or value == '':
                redacted_data[key] = value
                continue

            str_value = str(value).strip()
            redacted_value = str_value

            # Check for standalone PII (these are PII on their own)
            if key in ['phone', 'contact'] or self.is_phone_number(str_value):
                has_pii = True
                redacted_value = self.redact_text(str_value, 'phone')

            elif key == 'aadhar' or self.is_aadhar_number(str_value):
                has_pii = True
                redacted_value = self.redact_text(str_value, 'aadhar')

            elif key == 'passport' or self.is_passport_number(str_value):
                has_pii = True
                redacted_value = self.redact_text(str_value, 'passport')

            elif key == 'upi_id' or self.is_upi_id(str_value):
                has_pii = True
                redacted_value = self.redact_text(str_value, 'upi')

            # Collect combinatorial PII elements (only PII when combined)
            if key == 'name' or (key in ['first_name', 'last_name'] and 'name' not in data):
                if self.extract_names(str_value) or key in ['first_name', 'last_name']:
                    combinatorial_elements['name'].append(key)

            elif key == 'email' or self.is_email(str_value):
                combinatorial_elements['email'].append(key)

            elif key in ['address', 'city', 'pin_code', 'state']:
                combinatorial_elements['address'].append(key)

            elif key in ['device_id', 'ip_address']:
                combinatorial_elements[key].append(key)

            redacted_data[key] = redacted_value

        # Check for combinatorial PII (2 or more elements from different categories)
        combinatorial_count = sum(1 for elements in combinatorial_elements.values() if elements)

        if combinatorial_count >= 2:
            has_pii = True
            # Redact combinatorial elements
            for element_type, fields in combinatorial_elements.items():
                for field in fields:
                    if field in redacted_data:
                        if element_type == 'name':
                            redacted_data[field] = self.redact_text(str(redacted_data[field]), 'name')
                        elif element_type == 'email':
                            redacted_data[field] = self.redact_text(str(redacted_data[field]), 'email')
                        elif element_type in ['device_id', 'ip_address']:
                            redacted_data[field] = '[REDACTED_' + element_type.upper() + ']'

        return has_pii, redacted_data

    def process_csv(self, input_file: str, output_file: str = None):
        """Process CSV file and detect/redact PII"""
        if not output_file:
            # Generate output filename
            base_name = input_file.replace('.csv', '')
            output_file = 'redacted_output_Barath_S.csv'

        results = []

        try:
            # Try different encodings to handle various file formats
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            file_read = False

            for encoding in encodings:
                try:
                    with open(input_file, 'r', encoding=encoding) as f:
                        # Try to read the first line to check format
                        first_line = f.readline().strip()
                        f.seek(0)

                        print(f"Reading file with {encoding} encoding...")
                        print(f"First line preview: {first_line[:100]}...")

                        # Check if it looks like CSV
                        if ',' not in first_line and ';' in first_line:
                            # Try semicolon delimiter
                            reader = csv.DictReader(f, delimiter=';')
                        else:
                            reader = csv.DictReader(f)

                        # Process rows
                        row_count = 0
                        for row in reader:
                            row_count += 1

                            # Look for data_json column (case insensitive)
                            json_column = None
                            for col in row.keys():
                                if 'json' in col.lower() or col.lower() in ['data_json', 'Data_json']:
                                    json_column = col
                                    break

                            if json_column and row[json_column]:
                                try:
                                    # Parse JSON data
                                    json_data = json.loads(row[json_column])
                                    has_pii, redacted_data = self.analyze_record(json_data)

                                    result = {
                                        'record_id': row.get('record_id', str(row_count)),
                                        'redacted_data_json': json.dumps(redacted_data),
                                        'is_pii': has_pii
                                    }
                                    results.append(result)

                                except json.JSONDecodeError as je:
                                    print(f"JSON decode error in row {row_count}: {je}")
                                    # Handle invalid JSON
                                    result = {
                                        'record_id': row.get('record_id', str(row_count)),
                                        'redacted_data_json': row.get(json_column, ''),
                                        'is_pii': False
                                    }
                                    results.append(result)
                            else:
                                if row_count <= 5:  # Only show first few errors
                                    print(f"No JSON data found in row {row_count}, columns: {list(row.keys())}")

                        file_read = True
                        break

                except UnicodeDecodeError:
                    print(f"Failed to read with {encoding}, trying next encoding...")
                    continue
                except Exception as e:
                    print(f"Error with {encoding}: {e}")
                    continue

            if not file_read:
                raise Exception("Could not read file with any supported encoding")

            # Write results
            if results:
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['record_id', 'redacted_data_json', 'is_pii'])
                    writer.writeheader()
                    writer.writerows(results)

                print(f"\nProcessed {len(results)} records. Output saved to {output_file}")
                pii_count = sum(1 for r in results if r['is_pii'])
                if len(results) > 0:
                    print(f"PII detected in {pii_count} records ({pii_count/len(results)*100:.1f}%)")
                else:
                    print("No valid records found")
            else:
                print("\nNo records were processed. Please check:")
                print("1. File format (should be CSV with data_json column)")
                print("2. File encoding (trying utf-8, latin-1, etc.)")
                print("3. JSON format in data_json column")

        except FileNotFoundError:
            print(f"Error: Input file '{input_file}' not found.")
            print("Please check the file path and name.")
            sys.exit(1)
        except Exception as e:
            print(f"Error processing file: {str(e)}")
            sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python detector_Barath_S.py <input_csv_file>")
        print("Example: python detector_Barath_S.py 'iscp_pii_dataset_-_Sheet1.csv'")
        sys.exit(1)

    input_file = sys.argv[1]
    print(f"Starting PII detection for: {input_file}")
    print("Project Guardian 2.0 - PII Detection & Redaction")
    print("=" * 50)

    detector = PIIDetector()
    detector.process_csv(input_file)

    print("\n" + "=" * 50)
    print("PII Detection Complete!")
    print("Check the output file for redacted results.")


if __name__ == "__main__":
    main()
