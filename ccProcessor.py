import json
import boto3
import datetime
import random
from decimal import Decimal
import string
import time

dynamodb = boto3.resource('dynamodb')
bank_table = dynamodb.Table('Bank')
merchant_table = dynamodb.Table('Merchant')
transaction_table = dynamodb.Table('Transactions')

def lambda_handler(event, context):
    if 'body' in event and event['body'] is not None:
        body = event['body']
        bank_name = body.get('bank')
        merchant_name = body.get('merchant_name')
        merchant_id = body.get('merchant_token')  # Assuming you have merchant ID in the request
        cc_num = body.get('cc_num')
        card_type = body.get('card_type')
        amount = body.get('amount')
        timestamp = str(datetime.datetime.now())
        
        response_msg, status = process_transaction(merchant_name, merchant_id, cc_num, card_type, amount, bank_name)
        
        write_transaction_to_dynamodb(merchant_id, cc_num, amount, status)
        
        print(response_msg)
        return ok(response_msg)
        
        
def process_transaction_with_retry(merchant_name, merchant_id, cc_num, card_type, amount, bank_name):
    max_retries = 5
    retry_delay = 1
    
    for attempt in range(max_retries):
        response_msg, status = process_transaction(merchant_name, merchant_id, cc_num, card_type, amount, bank_name)
        
        if status == "Bank Not Available":
            print(f"Error detected: {response_msg} - retrying in {retry_delay} sec.")
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential back-off
        else:
            return response_msg, status
    
    return "Max retries exceeded. Could not process transaction.", "Max Retries Exceeded"

def process_transaction(merchant_name, merchant_id, cc_num, card_type, amount, bank_name):
    if random.random() < 0.1:
        return "Bank not available.", "Bank Not Available"
    
    card_msg = "Credit" if card_type.lower() == "credit" else "Debit"
    
    response = bank_table.get_item(
        Key={
            'BankName': bank_name,
            'AccountNum': cc_num
        }
    )
    
    if 'Item' in response:
        bank_info = response['Item']
        balance = Decimal(str(bank_info.get('Balance', 0)))
        amount_decimal = Decimal(str(amount))
        
        if balance >= amount_decimal:
            new_balance = balance - amount_decimal
            bank_table.update_item(
                Key={
                    'BankName': 'Bank of America',
                    'AccountNum': cc_num
                },
                UpdateExpression="SET Balance = :new_balance",
                ExpressionAttributeValues={':new_balance': new_balance}
            )
            return "Approved.", "Approved"
        else:
            return "Declined. Insufficient Funds.", "Declined"
    else:
        return "Error - Bad Bank or Account Number.", "Error"

def write_transaction_to_dynamodb(merchant_id, cc_num, amount, status):
    transaction_id = generate_transaction_id()
    
    transaction_item = {
        'TransactionID': transaction_id,
        'MerchantID': merchant_id,
        'ccNum': int(cc_num), 
        'Amount': Decimal(str(amount)),
        'DateTime': str(datetime.datetime.now()),
        'Status': status
    }
    
    response = transaction_table.put_item(Item=transaction_item)
    print("Transaction written to DynamoDB:", response)


def generate_transaction_id(length=10):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    random_chars = ''.join(random.choices(string.ascii_letters, k=length - len(timestamp)))
    random_nums = ''.join(random.choices(string.digits, k=length - len(timestamp)))
    transaction_id = timestamp + random_chars + random_nums
    return transaction_id


def ok(response_body):
    result = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html"
        },
        "body": response_body
    }
    return result
