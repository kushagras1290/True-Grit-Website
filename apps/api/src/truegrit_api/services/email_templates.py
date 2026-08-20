"""HTML Email Templates for Transactional Emails.

Uses inline CSS and tables for maximum cross-client compatibility.
"""

from __future__ import annotations

import html

# Base HTML wrapper with clean, modern styling
_BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica,
              Arial, sans-serif;
            background-color: #f7f9fc;
            margin: 0;
            padding: 0;
            -webkit-font-smoothing: antialiased;
        }}
        .email-wrapper {{
            width: 100%;
            background-color: #f7f9fc;
            padding: 40px 0;
        }}
        .email-container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05), 0 10px 15px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .header {{
            background-color: #0f5132;
            padding: 30px 40px;
            text-align: center;
        }}
        .header h1 {{
            color: #ffffff;
            margin: 0;
            font-size: 24px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        .content {{
            padding: 40px;
            color: #333333;
            line-height: 1.6;
            font-size: 16px;
        }}
        .footer {{
            background-color: #f1f5f9;
            padding: 20px 40px;
            text-align: center;
            color: #64748b;
            font-size: 13px;
            border-top: 1px solid #e2e8f0;
        }}
        .btn {{
            display: inline-block;
            background-color: #198754;
            color: #ffffff !important;
            text-decoration: none;
            padding: 14px 28px;
            border-radius: 6px;
            font-weight: 600;
            margin: 24px 0;
            text-align: center;
        }}
        .btn:hover {{
            background-color: #157347;
        }}
        .order-panel {{
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .order-detail {{
            margin: 8px 0;
        }}
        .order-detail strong {{
            color: #1e293b;
        }}
        p {{
            margin: 0 0 16px 0;
        }}
    </style>
</head>
<body>
    <div class="email-wrapper">
        <div class="email-container">
            <div class="header">
                <h1>{header_title}</h1>
            </div>
            <div class="content">
                {body_html}
            </div>
            <div class="footer">
                &copy; 2026 True Grit. All rights reserved.<br>
                <span style="font-size: 12px;">This is an automated message, please do not
                reply directly to this email.</span>
            </div>
        </div>
    </div>
</body>
</html>
"""


def render_password_reset(reset_url: str, minutes: int) -> str:
    """Renders the HTML for the password reset email."""
    subject = "Reset your True Grit password"
    header_title = "True Grit"

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Password Reset Request</h2>
    <p>We received a request to reset your password for your account.</p>
    <p>You can reset your password by clicking the button below. This link is valid for
    <strong>{minutes} minutes</strong>.</p>
    <div style="text-align: center;">
        <a href="{reset_url}" class="btn">Reset My Password</a>
    </div>
    <p style="margin-top: 24px; font-size: 14px; color: #64748b;">
        If the button doesn't work, copy and paste this URL into your browser:<br>
        <a href="{reset_url}" style="color: #198754; word-break: break-all;">{reset_url}</a>
    </p>
    <p style="margin-top: 24px; font-size: 14px; color: #64748b;">
        If you didn't ask to reset your password, you can safely ignore this email.
        Your password will remain unchanged.
    </p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


def render_customer_welcome(display_name: str, storefront_url: str) -> str:
    """Renders the HTML welcoming a customer who has just signed up.

    `display_name` is whatever the customer typed into the sign-up form, so it
    is HTML-escaped before interpolation — same treatment as the community
    submission templates below.
    """
    subject = "Welcome to True Grit"
    header_title = "True Grit"
    safe_name = html.escape(display_name)
    safe_url = html.escape(storefront_url, quote=True)

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {safe_name},</h2>
    <p>Your True Grit account is ready. You can now track orders, save delivery
    addresses and follow the farms behind everything you buy.</p>
    <div style="text-align: center;">
        <a href="{safe_url}" class="btn">Start exploring the market</a>
    </div>
    <p style="margin-top: 24px; font-size: 14px; color: #64748b;">
        If you did not create this account, please contact us and we will close it.
    </p>
    <p style="margin-bottom: 0;">Welcome aboard,<br>The True Grit Team</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


def render_staff_invitation(display_name: str, setup_url: str, minutes: int) -> str:
    """Renders the HTML for a staff admin invitation email.

    `display_name` is typed by whoever raised the invitation, so it is escaped
    for the same reason the community templates escape theirs.
    """
    subject = "You are invited to True Grit"
    header_title = "True Grit Admin"
    safe_display_name = html.escape(display_name)

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {safe_display_name},</h2>
    <p>You have been invited to the True Grit admin portal.</p>
    <p>Use the button below to set your password and activate your account. This link is
    valid for <strong>{minutes} minutes</strong>.</p>
    <div style="text-align: center;">
        <a href="{setup_url}" class="btn">Set My Password</a>
    </div>
    <p style="margin-top: 24px; font-size: 14px; color: #64748b;">
        If the button doesn't work, copy and paste this URL into your browser:<br>
        <a href="{setup_url}" style="color: #198754; word-break: break-all;">{setup_url}</a>
    </p>
    <p style="margin-bottom: 0;">Best regards,<br>The True Grit Team</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


def render_order_confirmation(customer_name: str, reference: str, total: str) -> str:
    """Renders the HTML for the customer order confirmation email."""
    subject = f"Order {reference} confirmed"
    header_title = "True Grit"

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {customer_name},</h2>
    <p>Thank you for shopping with True Grit! Your order has been successfully confirmed.</p>

    <div class="order-panel">
        <h3 style="margin-top: 0; color: #0f5132;">Order Summary</h3>
        <div class="order-detail"><strong>Order Reference:</strong> {reference}</div>
        <div class="order-detail"><strong>Total Amount:</strong> {total}</div>
        <div class="order-detail"><strong>Payment Method:</strong> Cash on Delivery</div>
    </div>

    <p>We are currently processing your order and will let you know as soon as it ships.</p>
    <p>If you have any questions, feel free to contact our support team.</p>
    <p style="margin-bottom: 0;">Best regards,<br>The True Grit Team</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


def render_refund_approved(customer_name: str, order_reference: str, amount_display: str) -> str:
    """Renders the HTML for a refund the refund orchestrator (or staff) has
    processed -- the amount has already been sent back through the original
    payment gateway by the time this is sent."""
    subject = f"Your refund for order {order_reference} has been processed"
    header_title = "True Grit"

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {customer_name},</h2>
    <p>Your return for order <strong>{order_reference}</strong> has been approved.</p>

    <div class="order-panel">
        <h3 style="margin-top: 0; color: #0f5132;">Refund Summary</h3>
        <div class="order-detail"><strong>Order Reference:</strong> {order_reference}</div>
        <div class="order-detail"><strong>Refunded Amount:</strong> {amount_display}</div>
    </div>

    <p>The amount above has been sent back to your original payment method. It may take a
    few business days to appear on your statement, depending on your bank or card issuer.</p>
    <p style="margin-bottom: 0;">Best regards,<br>The True Grit Team</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


def render_refund_denied(customer_name: str, order_reference: str, reason: str) -> str:
    """Renders the HTML declining a return's refund. `reason` is a
    plain-language rationale (never a raw fraud-signal id), the same
    treatment `render_farm_partnership_rejected` gives its own reason."""
    subject = f"About your return for order {order_reference}"
    header_title = "True Grit"
    safe_reason = html.escape(reason)

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {customer_name},</h2>
    <p>After review, we're not able to refund your return for order
    <strong>{order_reference}</strong>.</p>
    <div class="order-panel">
        <div class="order-detail">{safe_reason}</div>
    </div>
    <p>If you think this is a mistake, reply to this email and our team will take another
    look.</p>
    <p style="margin-bottom: 0;">The True Grit Team</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


def render_farm_order_notification(
    owner_name: str, farm_name: str, reference: str, admin_url: str
) -> str:
    """Renders the HTML for the farm owner new order notification."""
    subject = f"Order Received: {reference}"
    header_title = "True Grit Partner"

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {owner_name},</h2>
    <p>Good news! A new order has been received for <strong>{farm_name}</strong>.</p>

    <div class="order-panel">
        <h3 style="margin-top: 0; color: #0f5132;">Order Details</h3>
        <div class="order-detail"><strong>Order Reference:</strong> {reference}</div>
    </div>

    <p>Please check your dashboard to view the full order details and prepare the items
    for fulfilment.</p>
    <div style="text-align: center;">
        <a href="{admin_url}/orders" class="btn"
        style="background-color: #3b82f6;">Go to Dashboard</a>
    </div>
    <p style="margin-bottom: 0; margin-top: 24px;">Best regards,<br>The True Grit System</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


def render_submission_approved(contact_name: str, content_type: str, title: str, url: str) -> str:
    """Renders the HTML for a community blog/recipe submission that went live.

    `contact_name` and `title` come from public form input, so they are
    HTML-escaped before interpolation -- unlike the other templates in this
    file, whose inputs are staff/customer account fields validated at
    registration.
    """
    kind = "blog post" if content_type == "article" else "recipe"
    subject = f"Your {kind} is live on True Grit"
    header_title = "True Grit"
    safe_name = html.escape(contact_name)
    safe_title = html.escape(title)

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {safe_name},</h2>
    <p>Great news — your {kind} <strong>&ldquo;{safe_title}&rdquo;</strong> has been
    approved and is now live on True Grit.</p>
    <div style="text-align: center;">
        <a href="{url}" class="btn">View it live</a>
    </div>
    <p style="margin-bottom: 0;">Thanks for contributing to the community!<br>The True Grit Team</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


def render_submission_changes_requested(
    contact_name: str, content_type: str, title: str, note: str, edit_url: str
) -> str:
    """Renders the HTML asking a community contributor to revise a submission."""
    kind = "blog post" if content_type == "article" else "recipe"
    subject = f"Changes requested on your {kind} submission"
    header_title = "True Grit"
    safe_name = html.escape(contact_name)
    safe_title = html.escape(title)
    safe_note = html.escape(note)

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {safe_name},</h2>
    <p>Thanks for submitting your {kind} <strong>&ldquo;{safe_title}&rdquo;</strong>. Our
    editors would like a few changes before it can be published:</p>
    <div class="order-panel">
        <div class="order-detail">{safe_note}</div>
    </div>
    <div style="text-align: center;">
        <a href="{edit_url}" class="btn">Edit and resubmit</a>
    </div>
    <p style="margin-bottom: 0;">The True Grit Team</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


def render_submission_rejected(
    contact_name: str, content_type: str, title: str, reason: str
) -> str:
    """Renders the HTML declining a community blog/recipe submission."""
    kind = "blog post" if content_type == "article" else "recipe"
    subject = f"About your {kind} submission"
    header_title = "True Grit"
    safe_name = html.escape(contact_name)
    safe_title = html.escape(title)
    safe_reason = html.escape(reason)

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {safe_name},</h2>
    <p>Thank you for submitting your {kind} <strong>&ldquo;{safe_title}&rdquo;</strong>.
    After review, we won't be publishing it this time.</p>
    <div class="order-panel">
        <div class="order-detail">{safe_reason}</div>
    </div>
    <p style="margin-bottom: 0;">We'd love to see future submissions from you.<br>
    The True Grit Team</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


# --------------------------------------------------------------------------
# Farm partnership applications
#
# Every input to these three templates comes from an unauthenticated public
# form, so all of it is HTML-escaped before interpolation -- there is no
# account validation upstream to lean on, unlike the order and reset templates
# above whose inputs are account fields.
# --------------------------------------------------------------------------


def render_farm_partnership_received(contact_name: str, farm_name: str) -> str:
    """Acknowledges a farm partnership application to the grower who sent it.

    Worth sending on its own: without it the form is a void, and the most
    common consequence of a void is the same application submitted four more
    times.
    """
    subject = "We have your farm application"
    header_title = "True Grit"
    safe_name = html.escape(contact_name)
    safe_farm = html.escape(farm_name)

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {safe_name},</h2>
    <p>Thank you for telling us about <strong>{safe_farm}</strong>. Your application to
    supply True Grit has reached our sourcing team.</p>
    <p>Someone will read it properly and call you on the number you gave us. We look at
    growing practices, certification and how far the produce has to travel, so the first
    conversation is usually a few questions rather than a decision.</p>
    <p style="margin-bottom: 0;">Thanks for thinking of us.<br>The True Grit Team</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


def render_farm_partnership_approved(contact_name: str, farm_name: str, note: str) -> str:
    """Tells a grower their farm has been accepted.

    `note` is optional here, unlike on the rejection: an acceptance is not made
    confusing by the absence of a reason.
    """
    subject = "Your farm application has been accepted"
    header_title = "True Grit"
    safe_name = html.escape(contact_name)
    safe_farm = html.escape(farm_name)
    note_html = (
        f"""
    <div class="order-panel">
        <div class="order-detail">{html.escape(note)}</div>
    </div>
    """
        if note
        else ""
    )

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {safe_name},</h2>
    <p>Good news — we would like to work with <strong>{safe_farm}</strong>.</p>
    {note_html}
    <p>Our sourcing team will be in touch to walk through certification paperwork,
    pricing and delivery before anything of yours goes on sale.</p>
    <p style="margin-bottom: 0;">Welcome aboard.<br>The True Grit Team</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)


def render_farm_partnership_rejected(contact_name: str, farm_name: str, reason: str) -> str:
    """Declines a farm partnership application. The reason is mandatory at the
    service layer, because "no" with no explanation is the outcome that
    reliably produces a second identical application."""
    subject = "About your farm application"
    header_title = "True Grit"
    safe_name = html.escape(contact_name)
    safe_farm = html.escape(farm_name)
    safe_reason = html.escape(reason)

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {safe_name},</h2>
    <p>Thank you for telling us about <strong>{safe_farm}</strong>. After reading your
    application, we are not able to take it further right now.</p>
    <div class="order-panel">
        <div class="order-detail">{safe_reason}</div>
    </div>
    <p style="margin-bottom: 0;">What we can take changes with the season and with what
    our customers ask for, so please do get in touch again.<br>The True Grit Team</p>
    """

    return _BASE_HTML.format(subject=subject, header_title=header_title, body_html=body_html)
