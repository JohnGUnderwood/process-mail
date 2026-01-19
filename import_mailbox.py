import mailbox
from email.header import decode_header
import json
import uuid
import os

# Create folder for processed mail if it doesn't exist
if not os.path.exists('processed_mail'):
    os.makedirs('processed_mail')

# List mbox files in the specified directory
mbox_dir = 'C:/Users/john/mbox/'
mbox_files = [f for f in os.listdir(mbox_dir) if f.endswith('.mbox')]

for mbox_file in mbox_files:
    # Open and iterate through mbox file
    mbox_name = mbox_file[:-5]  # Remove .mbox extension
    mbox = mailbox.mbox(f'C:/Users/john/mbox/{mbox_file}')

    # Create folder for this file if it doesn't exist
    if not os.path.exists(os.path.join('processed_mail', mbox_name)):
        os.makedirs(os.path.join('processed_mail', mbox_name))

    batch_size = 1000
    batch = []
    batch_count = 0
    for message in mbox:
        # Extract email components - decode if needed
        def decode_field(field_value):
            if not field_value:
                return ''
            try:
                decoded_parts = []
                for text, encoding in decode_header(field_value):
                    if isinstance(text, bytes):
                        try:
                            decoded_parts.append(text.decode(encoding or 'utf-8', errors='replace'))
                        except (LookupError, TypeError):
                            decoded_parts.append(text.decode('utf-8', errors='replace'))
                    else:
                        decoded_parts.append(str(text))
                return ''.join(decoded_parts)
            except Exception:
                return str(field_value)
        
        subject = decode_field(message['subject'])
        from_addr = decode_field(message['from'])
        to_addr = decode_field(message['to'])
        date = str(message['date']) if message['date'] else ''
        
        # Create deterministic UUID from key fields
        hash_input = f"{subject}|{from_addr}|{to_addr}|{date}"
        email_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, hash_input))
        
        # Get email body
        body = ''
        try:
            if message.is_multipart():
                for part in message.walk():
                    if part.get_content_type() == 'text/plain':
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = message.get_payload(decode=True).decode()
        except (UnicodeDecodeError, AttributeError):
            body = ''

        # Create json for the email
        email_json = {
            'uuid': email_id,
            'uuid_version': 5,
            'uuid_input': hash_input,
            'subject': subject,
            'from': from_addr,
            'to': to_addr,
            'date': date,
            'body': body
        }

        batch.append(email_json)
        # If batch size reached, write to file and reset batch
        if len(batch) >= batch_size:
            with open(os.path.join('processed_mail',mbox_name, f'{mbox_name}_{batch_count}.jsonl'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(json.dumps(email, ensure_ascii=False) for email in batch) + '\n')
            batch = []
            batch_count += 1

    # Write any remaining emails in the last batch
    if len(batch) > 0:
        with open(os.path.join('processed_mail',mbox_name, f'{mbox_name}_{batch_count}.jsonl'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(json.dumps(email, ensure_ascii=False) for email in batch) + '\n')
    
    # Close the mbox file before deleting
    mbox.close()
    
    # Finally delete the processed mbox file
    os.remove(f'C:/Users/john/mbox/{mbox_file}')