import json
from flask import Flask, jsonify, request, render_template, redirect, abort, Response
import requests


client_id = "AUU7w_Ti2LBh9VemXVY4GVkS-s9WHAGvOEGtfZRB72QgHLIUM1tYS98jzm3FJYx6Pg40o1nK_elc-8rY"
client_secret = "EPnQAoD4U0_z14zEOiGkhp9pNyNQqHIwHfKv4SRuBrXw7fSl169K_8wwXT2JURpk6Qy2x7U-mf4Uh4Ue"

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False


# Common function to generate access token whenever required
def generate_access_token():
    act_headers = {
        'Accept': 'application/json',
        'Accept-Language': 'en_US'
    }
    act_data = {
        'grant_type': 'client_credentials'
    }
    act_url = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
    act_resp = requests.post(
        url=act_url,
        headers=act_headers,
        data=act_data,
        auth=(client_id, client_secret)
    ).text
    access_token = json.loads(act_resp)["access_token"]
    return f"Bearer {access_token}"



@app.route('/', methods=['GET', 'POST'])
def choose_plan():
    """
    If request method if GET, client is trying to access localhost:5000/ (or the home page)
    In that case, show them the "choose_plan.html" template which asks them to fill a form

    If request type is POST, read data from form, generate access token and create order
    From create order response, get the link
    """
    if request.method == "POST":
        # Store the amount received from the form as float
        amount_entered = float(request.form.get('amount'))
        
        # Generate access token using generate_access_token function defined above
        authorization = generate_access_token()

        # Create an order and redirect user to the link from that response.
        # Use the authorization created above for authentication purpose.
        ord_body = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": "USD",
                        "value": amount_entered  # This is the amount entered by customer
                    }
                }
            ],
            "application_context": {
                "user_action": "PAY_NOW",
                "return_url": "http://localhost:5000/payment_success/",
                "cancel_url": "http://localhost:5000/payment_cancelled/"
            }
        }
        ord_headers = {
            "Content-Type": "application/json",
            "Authorization": authorization
        }
        ord_url = "https://api-m.sandbox.paypal.com/v2/checkout/orders"
        ord_resp = requests.post(
            url=ord_url,
            data=json.dumps(ord_body),
            headers=ord_headers
        )
        ord_parse = json.loads(ord_resp.text)
        
        # Iterate over the links array from the response above.
        for link in ord_parse["links"]:
            if link["rel"] == "approve":
                # If "rel" is "approve" redirect user to that for payment.
                redirect_url = link["href"]
                return redirect(redirect_url)
    return render_template('choose_plan.html')

@app.route('/payment_success/', methods=['GET', 'POST'])
def payment_success():
    order_id = request.args.get('token')
    if not order_id:
        abort(404)
    authorization = generate_access_token()
    ord_valid_headers = {
        "Content-Type": "application/json",
        "Authorization": authorization
    }
    ord_valid_resp = requests.get(
        url=f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{order_id}",
        headers=ord_valid_headers
    )
    ord_valid_resp_parse = json.loads(ord_valid_resp.text)
    if ord_valid_resp_parse.get('name'):
        abort(403)
    capture_resp = requests.post(
        url=f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{order_id}/capture",
        headers=ord_valid_headers
    )
    capture_resp_parse = json.loads(capture_resp.text)
    if capture_resp_parse.get('name'):
        abort(403)
    address_1 = capture_resp_parse["purchase_units"][0]["shipping"]["address"].get("address_line_1")
    address_2 = capture_resp_parse["purchase_units"][0]["shipping"]["address"].get("address_line_2")
    
    # If address_2 not None or not False
    if address_2:
        address = f"{address_1}, {address_2}"
    else:
        address = address_1

    state = capture_resp_parse["purchase_units"][0]["shipping"]["address"].get("admin_area_1")
    city = capture_resp_parse["purchase_units"][0]["shipping"]["address"]["admin_area_2"]
    country = capture_resp_parse["purchase_units"][0]["shipping"]["address"]["country_code"]
    postal_code = capture_resp_parse["purchase_units"][0]["shipping"]["address"]["postal_code"]
    if capture_resp_parse["status"] == "COMPLETED":
        status = "Order completed"
    else:
        status = "Order not completed"
    success_response = {
        'Message': 'Your payment is successful. Please see details below',
        'Order Details': {
            "Order ID": order_id,
            "Currency Code": capture_resp_parse["purchase_units"][0]["payments"]["captures"][0]["amount"]["currency_code"],
            "Amount": float(capture_resp_parse["purchase_units"][0]["payments"]["captures"][0]["amount"]["value"]),
            "Status": status
        },
        'Customer Details': {
            'Name': f'{capture_resp_parse["payer"]["name"]["given_name"]} {capture_resp_parse["payer"]["name"]["surname"]}',
            'Email': capture_resp_parse["payer"]["email_address"],
            'Street Address': address,
            'City': city,
            'State': state,
            'Country': country,
            'Postal Code': postal_code
        },
        'Home Page': 'http://localhost:5000/'
    }
    return Response(json.dumps(success_response, indent=2), mimetype='application/json')


@app.route('/payment_cancelled/', methods=['GET', 'POST'])
def payment_cancelled():
    return jsonify(
        {
            "Message": "Payment has been cancelled by you!",
            "Home Page": "http://localhost:5000/"
        }
    )


if __name__ == '__main__':
    app.run(debug=True)
