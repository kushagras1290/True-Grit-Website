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


def render_staff_invitation(display_name: str, setup_url: str, minutes: int) -> str:
    """Renders the HTML for a staff admin invitation email."""
    subject = "You are invited to True Grit"
    header_title = "True Grit Admin"

    body_html = f"""
    <h2 style="color: #1e293b; margin-top: 0;">Hi {display_name},</h2>
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
