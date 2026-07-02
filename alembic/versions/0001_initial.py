"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-06-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enum types ────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE productstatus AS ENUM ('active', 'inactive', 'out_of_stock', 'discontinued')")
    op.execute("CREATE TYPE templatestatus AS ENUM ('pending', 'approved', 'rejected', 'paused')")
    op.execute("CREATE TYPE campaigntype AS ENUM ('whatsapp', 'email', 'sms', 'multi_channel')")
    op.execute("CREATE TYPE campaignstatus AS ENUM ('draft', 'scheduled', 'running', 'paused', 'completed', 'cancelled')")
    op.execute("CREATE TYPE companysize AS ENUM ('micro', 'small', 'medium', 'large', 'enterprise')")
    op.execute("CREATE TYPE documentstatus AS ENUM ('pending', 'processing', 'ready', 'failed')")
    op.execute("CREATE TYPE notificationtype AS ENUM ('info', 'success', 'warning', 'error', 'reminder', 'lead', 'task', 'ticket', 'campaign', 'appointment', 'system')")
    op.execute("CREATE TYPE customergender AS ENUM ('male', 'female', 'other', 'unknown')")
    op.execute("CREATE TYPE customerstatus AS ENUM ('active', 'inactive', 'blocked', 'prospect')")
    op.execute("CREATE TYPE activitytype AS ENUM ('call', 'email', 'whatsapp', 'meeting', 'note', 'task', 'lead_created', 'lead_updated', 'order_placed', 'payment_received', 'ticket_opened', 'ticket_resolved', 'campaign_sent', 'ai_interaction', 'status_change', 'other')")
    op.execute("CREATE TYPE appointmenttype AS ENUM ('call', 'video_call', 'in_person', 'demo', 'consultation', 'follow_up', 'other')")
    op.execute("CREATE TYPE appointmentstatus AS ENUM ('scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show', 'rescheduled')")
    op.execute("CREATE TYPE recipientstatus AS ENUM ('pending', 'sent', 'delivered', 'read', 'failed', 'opted_out')")
    op.execute("CREATE TYPE conversationstatus AS ENUM ('open', 'in_progress', 'waiting', 'resolved', 'closed', 'bot_handling', 'escalated')")
    op.execute("CREATE TYPE leadstatus AS ENUM ('new', 'contacted', 'qualified', 'proposal', 'negotiation', 'won', 'lost', 'disqualified')")
    op.execute("CREATE TYPE leadpriority AS ENUM ('low', 'medium', 'high', 'urgent')")
    op.execute("CREATE TYPE leadsource AS ENUM ('whatsapp', 'website', 'referral', 'social', 'email', 'cold_call', 'event', 'other')")
    op.execute("CREATE TYPE orderstatus AS ENUM ('draft', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded')")
    op.execute("CREATE TYPE paymentstatus AS ENUM ('pending', 'partial', 'paid', 'failed', 'refunded')")
    op.execute("CREATE TYPE ticketstatus AS ENUM ('open', 'in_progress', 'waiting', 'resolved', 'closed')")
    op.execute("CREATE TYPE ticketpriority AS ENUM ('low', 'medium', 'high', 'urgent')")
    op.execute("CREATE TYPE messagedirection AS ENUM ('inbound', 'outbound')")
    op.execute("CREATE TYPE messagetype AS ENUM ('text', 'image', 'audio', 'video', 'document', 'location', 'contact', 'sticker', 'interactive', 'template', 'system', 'reaction', 'unsupported')")
    op.execute("CREATE TYPE followuptype AS ENUM ('whatsapp', 'email', 'call', 'sms', 'task')")
    op.execute("CREATE TYPE followupstatus AS ENUM ('pending', 'sent', 'completed', 'skipped')")
    op.execute("CREATE TYPE taskstatus AS ENUM ('todo', 'in_progress', 'review', 'done', 'cancelled')")
    op.execute("CREATE TYPE taskpriority AS ENUM ('low', 'medium', 'high', 'urgent')")

    # ── Tables ────────────────────────────────────────────────────────────────
    op.execute("""
CREATE TABLE lead_stages (
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	"order" INTEGER NOT NULL, 
	color VARCHAR(20), 
	is_won BOOLEAN NOT NULL, 
	is_lost BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_lead_stages PRIMARY KEY (id)
);
""")

    op.execute("""
CREATE TABLE permissions (
	name VARCHAR(100) NOT NULL, 
	codename VARCHAR(100) NOT NULL, 
	description TEXT, 
	resource VARCHAR(100) NOT NULL, 
	action VARCHAR(50) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_permissions PRIMARY KEY (id), 
	CONSTRAINT uq_permissions_resource_action UNIQUE (resource, action)
);
""")

    op.execute("""
CREATE TABLE products (
	name VARCHAR(255) NOT NULL, 
	sku VARCHAR(100), 
	description TEXT, 
	category VARCHAR(100), 
	unit VARCHAR(50), 
	price FLOAT NOT NULL, 
	cost FLOAT, 
	tax_rate FLOAT NOT NULL, 
	discount FLOAT NOT NULL, 
	stock_quantity INTEGER NOT NULL, 
	min_stock_level INTEGER NOT NULL, 
	status productstatus NOT NULL, 
	is_featured BOOLEAN NOT NULL, 
	image_url TEXT, 
	custom_fields JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_products PRIMARY KEY (id), 
	CONSTRAINT uq_products_sku UNIQUE (sku)
);
""")

    op.execute("""
CREATE TABLE roles (
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	is_system BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_roles PRIMARY KEY (id)
);
""")

    op.execute("""
CREATE TABLE tags (
	name VARCHAR(100) NOT NULL, 
	color VARCHAR(20), 
	description VARCHAR(255), 
	entity_type VARCHAR(50) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_tags PRIMARY KEY (id)
);
""")

    op.execute("""
CREATE TABLE users (
	email VARCHAR(255) NOT NULL, 
	username VARCHAR(100) NOT NULL, 
	hashed_password VARCHAR(255) NOT NULL, 
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100) NOT NULL, 
	phone VARCHAR(20), 
	avatar_url TEXT, 
	is_active BOOLEAN NOT NULL, 
	is_verified BOOLEAN NOT NULL, 
	is_superuser BOOLEAN NOT NULL, 
	email_verified_at TIMESTAMP WITH TIME ZONE, 
	last_login_at TIMESTAMP WITH TIME ZONE, 
	password_changed_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_users PRIMARY KEY (id)
);
""")

    op.execute("""
CREATE TABLE whatsapp_templates (
	name VARCHAR(255) NOT NULL, 
	language VARCHAR(10) NOT NULL, 
	category VARCHAR(50) NOT NULL, 
	status templatestatus NOT NULL, 
	header_type VARCHAR(50), 
	header_content TEXT, 
	body TEXT NOT NULL, 
	footer TEXT, 
	buttons JSONB, 
	components JSONB, 
	whatsapp_template_id VARCHAR(255), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_whatsapp_templates PRIMARY KEY (id)
);
""")

    op.execute("""
CREATE TABLE calendar_credentials (
	user_id UUID NOT NULL, 
	access_token_encrypted TEXT NOT NULL, 
	refresh_token_encrypted TEXT NOT NULL, 
	token_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	calendar_id VARCHAR(255) NOT NULL, 
	scope TEXT, 
	is_active BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_calendar_credentials PRIMARY KEY (id), 
	CONSTRAINT fk_calendar_credentials_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
""")

    op.execute("""
CREATE TABLE campaigns (
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	campaign_type campaigntype NOT NULL, 
	status campaignstatus NOT NULL, 
	created_by UUID, 
	message_template TEXT NOT NULL, 
	whatsapp_template_name VARCHAR(255), 
	subject VARCHAR(255), 
	scheduled_at TIMESTAMP WITH TIME ZONE, 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	total_recipients INTEGER NOT NULL, 
	sent_count INTEGER NOT NULL, 
	delivered_count INTEGER NOT NULL, 
	read_count INTEGER NOT NULL, 
	failed_count INTEGER NOT NULL, 
	audience_filters JSONB, 
	metadata JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_campaigns PRIMARY KEY (id), 
	CONSTRAINT fk_campaigns_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE companies (
	name VARCHAR(255) NOT NULL, 
	domain VARCHAR(255), 
	industry VARCHAR(100), 
	size companysize, 
	employee_count INTEGER, 
	annual_revenue FLOAT, 
	phone VARCHAR(30), 
	email VARCHAR(255), 
	website VARCHAR(255), 
	linkedin_url VARCHAR(255), 
	country VARCHAR(100), 
	city VARCHAR(100), 
	address TEXT, 
	description TEXT, 
	logo_url TEXT, 
	assigned_to UUID, 
	custom_fields JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_companies PRIMARY KEY (id), 
	CONSTRAINT uq_companies_domain UNIQUE (domain), 
	CONSTRAINT fk_companies_assigned_to_users FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE knowledge_documents (
	title VARCHAR(255) NOT NULL, 
	description TEXT, 
	file_name VARCHAR(255), 
	file_url TEXT, 
	source_url TEXT, 
	doc_type VARCHAR(50) NOT NULL, 
	status documentstatus NOT NULL, 
	uploaded_by UUID, 
	total_chunks INTEGER NOT NULL, 
	error_message TEXT, 
	metadata JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_knowledge_documents PRIMARY KEY (id), 
	CONSTRAINT fk_knowledge_documents_uploaded_by_users FOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE notifications (
	user_id UUID NOT NULL, 
	notification_type notificationtype NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	body TEXT NOT NULL, 
	is_read BOOLEAN NOT NULL, 
	read_at TIMESTAMP WITH TIME ZONE, 
	entity_type VARCHAR(50), 
	entity_id UUID, 
	action_url TEXT, 
	metadata JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_notifications PRIMARY KEY (id), 
	CONSTRAINT fk_notifications_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
""")

    op.execute("""
CREATE TABLE refresh_tokens (
	user_id UUID NOT NULL, 
	token_hash VARCHAR(255) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	device_info TEXT, 
	ip_address VARCHAR(45), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_refresh_tokens PRIMARY KEY (id), 
	CONSTRAINT fk_refresh_tokens_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
""")

    op.execute("""
CREATE TABLE role_permissions (
	role_id UUID NOT NULL, 
	permission_id UUID NOT NULL, 
	CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_id), 
	CONSTRAINT fk_role_permissions_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
	CONSTRAINT fk_role_permissions_permission_id_permissions FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);
""")

    op.execute("""
CREATE TABLE user_roles (
	user_id UUID NOT NULL, 
	role_id UUID NOT NULL, 
	CONSTRAINT pk_user_roles PRIMARY KEY (user_id, role_id), 
	CONSTRAINT fk_user_roles_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_user_roles_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
);
""")

    op.execute("""
CREATE TABLE customers (
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100) NOT NULL, 
	email VARCHAR(255), 
	phone VARCHAR(30) NOT NULL, 
	whatsapp_id VARCHAR(30), 
	gender customergender NOT NULL, 
	avatar_url TEXT, 
	status customerstatus NOT NULL, 
	is_verified BOOLEAN NOT NULL, 
	country VARCHAR(100), 
	city VARCHAR(100), 
	address TEXT, 
	timezone VARCHAR(50), 
	language VARCHAR(10), 
	job_title VARCHAR(150), 
	industry VARCHAR(100), 
	company_id UUID, 
	assigned_to UUID, 
	lead_score INTEGER NOT NULL, 
	lifetime_value FLOAT NOT NULL, 
	total_orders INTEGER NOT NULL, 
	sentiment_score FLOAT, 
	intent_summary TEXT, 
	ai_notes TEXT, 
	source VARCHAR(100), 
	custom_fields JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_customers PRIMARY KEY (id), 
	CONSTRAINT fk_customers_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE SET NULL, 
	CONSTRAINT fk_customers_assigned_to_users FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE document_chunks (
	document_id UUID NOT NULL, 
	chunk_index INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	embedding JSONB, 
	token_count INTEGER NOT NULL, 
	metadata JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_document_chunks PRIMARY KEY (id), 
	CONSTRAINT fk_document_chunks_document_id_knowledge_documents FOREIGN KEY(document_id) REFERENCES knowledge_documents (id) ON DELETE CASCADE
);
""")

    op.execute("""
CREATE TABLE activities (
	customer_id UUID NOT NULL, 
	user_id UUID, 
	activity_type activitytype NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	description TEXT, 
	entity_type VARCHAR(50), 
	entity_id UUID, 
	metadata JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_activities PRIMARY KEY (id), 
	CONSTRAINT fk_activities_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE, 
	CONSTRAINT fk_activities_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE appointments (
	title VARCHAR(255) NOT NULL, 
	description TEXT, 
	appointment_type appointmenttype NOT NULL, 
	status appointmentstatus NOT NULL, 
	customer_id UUID NOT NULL, 
	assigned_to UUID, 
	start_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	end_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	timezone VARCHAR(50) NOT NULL, 
	location VARCHAR(255), 
	meeting_url TEXT, 
	google_event_id VARCHAR(255), 
	reminder_sent BOOLEAN NOT NULL, 
	reminder_minutes_before INTEGER NOT NULL, 
	cancellation_reason TEXT, 
	notes TEXT, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_appointments PRIMARY KEY (id), 
	CONSTRAINT fk_appointments_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE, 
	CONSTRAINT fk_appointments_assigned_to_users FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE campaign_recipients (
	campaign_id UUID NOT NULL, 
	customer_id UUID NOT NULL, 
	status recipientstatus NOT NULL, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	delivered_at TIMESTAMP WITH TIME ZONE, 
	read_at TIMESTAMP WITH TIME ZONE, 
	error_message TEXT, 
	whatsapp_message_id VARCHAR(255), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_campaign_recipients PRIMARY KEY (id), 
	CONSTRAINT fk_campaign_recipients_campaign_id_campaigns FOREIGN KEY(campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE, 
	CONSTRAINT fk_campaign_recipients_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE
);
""")

    op.execute("""
CREATE TABLE conversations (
	customer_id UUID NOT NULL, 
	assigned_to UUID, 
	whatsapp_conversation_id VARCHAR(255), 
	phone_number VARCHAR(30) NOT NULL, 
	status conversationstatus NOT NULL, 
	is_bot_active BOOLEAN NOT NULL, 
	last_message_at TIMESTAMP WITH TIME ZONE, 
	last_message_preview VARCHAR(255), 
	unread_count INTEGER NOT NULL, 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	sentiment VARCHAR(50), 
	sentiment_score FLOAT, 
	intent VARCHAR(100), 
	language VARCHAR(10), 
	urgency VARCHAR(50), 
	ai_summary TEXT, 
	metadata JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_conversations PRIMARY KEY (id), 
	CONSTRAINT fk_conversations_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE, 
	CONSTRAINT fk_conversations_assigned_to_users FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE leads (
	title VARCHAR(255) NOT NULL, 
	description TEXT, 
	customer_id UUID NOT NULL, 
	assigned_to UUID, 
	stage_id UUID, 
	status leadstatus NOT NULL, 
	priority leadpriority NOT NULL, 
	source leadsource NOT NULL, 
	estimated_value FLOAT, 
	probability FLOAT, 
	expected_close_date VARCHAR(30), 
	lead_score INTEGER NOT NULL, 
	buying_intent VARCHAR(50), 
	budget_range VARCHAR(100), 
	timeline VARCHAR(100), 
	is_decision_maker BOOLEAN, 
	purchase_probability FLOAT, 
	urgency VARCHAR(50), 
	lost_reason TEXT, 
	custom_fields JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_leads PRIMARY KEY (id), 
	CONSTRAINT fk_leads_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE, 
	CONSTRAINT fk_leads_assigned_to_users FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_leads_stage_id_lead_stages FOREIGN KEY(stage_id) REFERENCES lead_stages (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE orders (
	order_number VARCHAR(50) NOT NULL, 
	customer_id UUID NOT NULL, 
	assigned_to UUID, 
	status orderstatus NOT NULL, 
	payment_status paymentstatus NOT NULL, 
	subtotal FLOAT NOT NULL, 
	tax_amount FLOAT NOT NULL, 
	discount_amount FLOAT NOT NULL, 
	shipping_amount FLOAT NOT NULL, 
	total_amount FLOAT NOT NULL, 
	currency VARCHAR(10) NOT NULL, 
	shipping_address TEXT, 
	billing_address TEXT, 
	notes TEXT, 
	custom_fields JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_orders PRIMARY KEY (id), 
	CONSTRAINT fk_orders_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_orders_assigned_to_users FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE support_tickets (
	ticket_number VARCHAR(50) NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	description TEXT NOT NULL, 
	customer_id UUID NOT NULL, 
	assigned_to UUID, 
	status ticketstatus NOT NULL, 
	priority ticketpriority NOT NULL, 
	category VARCHAR(100), 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	first_response_at TIMESTAMP WITH TIME ZONE, 
	resolution_notes TEXT, 
	satisfaction_rating INTEGER, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_support_tickets PRIMARY KEY (id), 
	CONSTRAINT fk_support_tickets_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE, 
	CONSTRAINT fk_support_tickets_assigned_to_users FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE conversation_messages (
	conversation_id UUID NOT NULL, 
	sender_id UUID, 
	whatsapp_message_id VARCHAR(255), 
	direction messagedirection NOT NULL, 
	message_type messagetype NOT NULL, 
	content TEXT, 
	media_url TEXT, 
	media_mime_type VARCHAR(100), 
	caption TEXT, 
	is_read BOOLEAN NOT NULL, 
	is_delivered BOOLEAN NOT NULL, 
	is_failed BOOLEAN NOT NULL, 
	error_message TEXT, 
	delivered_at TIMESTAMP WITH TIME ZONE, 
	read_at TIMESTAMP WITH TIME ZONE, 
	ai_processed BOOLEAN NOT NULL, 
	extracted_entities JSONB, 
	intent VARCHAR(100), 
	raw_payload JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_conversation_messages PRIMARY KEY (id), 
	CONSTRAINT fk_conversation_messages_conversation_id_conversations FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, 
	CONSTRAINT fk_conversation_messages_sender_id_users FOREIGN KEY(sender_id) REFERENCES users (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE conversation_summaries (
	conversation_id UUID NOT NULL, 
	customer_id UUID NOT NULL, 
	summary TEXT NOT NULL, 
	key_points JSONB, 
	action_items JSONB, 
	entities_extracted JSONB, 
	sentiment VARCHAR(50), 
	intent VARCHAR(100), 
	message_count INTEGER NOT NULL, 
	embedding JSONB, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_conversation_summaries PRIMARY KEY (id), 
	CONSTRAINT fk_conversation_summaries_conversation_id_conversations FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, 
	CONSTRAINT fk_conversation_summaries_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE
);
""")

    op.execute("""
CREATE TABLE follow_ups (
	customer_id UUID NOT NULL, 
	assigned_to UUID, 
	lead_id UUID, 
	follow_up_type followuptype NOT NULL, 
	status followupstatus NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	message TEXT, 
	scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	ai_generated BOOLEAN NOT NULL, 
	notes TEXT, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_follow_ups PRIMARY KEY (id), 
	CONSTRAINT fk_follow_ups_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE, 
	CONSTRAINT fk_follow_ups_assigned_to_users FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_follow_ups_lead_id_leads FOREIGN KEY(lead_id) REFERENCES leads (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE notes (
	customer_id UUID NOT NULL, 
	created_by UUID, 
	lead_id UUID, 
	title VARCHAR(255), 
	content TEXT NOT NULL, 
	is_pinned BOOLEAN NOT NULL, 
	is_ai_generated BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_notes PRIMARY KEY (id), 
	CONSTRAINT fk_notes_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE, 
	CONSTRAINT fk_notes_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_notes_lead_id_leads FOREIGN KEY(lead_id) REFERENCES leads (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE order_items (
	order_id UUID NOT NULL, 
	product_id UUID NOT NULL, 
	product_name VARCHAR(255) NOT NULL, 
	quantity INTEGER NOT NULL, 
	unit_price FLOAT NOT NULL, 
	discount FLOAT NOT NULL, 
	total_price FLOAT NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_order_items PRIMARY KEY (id), 
	CONSTRAINT fk_order_items_order_id_orders FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE, 
	CONSTRAINT fk_order_items_product_id_products FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE RESTRICT
);
""")

    op.execute("""
CREATE TABLE payments (
	order_id UUID NOT NULL, 
	amount FLOAT NOT NULL, 
	currency VARCHAR(10) NOT NULL, 
	method VARCHAR(50) NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	transaction_id VARCHAR(255), 
	gateway VARCHAR(100), 
	gateway_response JSONB, 
	notes TEXT, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_payments PRIMARY KEY (id), 
	CONSTRAINT fk_payments_order_id_orders FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE RESTRICT
);
""")

    op.execute("""
CREATE TABLE tasks (
	title VARCHAR(255) NOT NULL, 
	description TEXT, 
	status taskstatus NOT NULL, 
	priority taskpriority NOT NULL, 
	assigned_to UUID, 
	created_by UUID, 
	customer_id UUID, 
	lead_id UUID, 
	due_date TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	estimated_hours FLOAT, 
	actual_hours FLOAT, 
	tags TEXT, 
	notes TEXT, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_tasks PRIMARY KEY (id), 
	CONSTRAINT fk_tasks_assigned_to_users FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_tasks_created_by_users FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL, 
	CONSTRAINT fk_tasks_customer_id_customers FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE SET NULL, 
	CONSTRAINT fk_tasks_lead_id_leads FOREIGN KEY(lead_id) REFERENCES leads (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE ticket_messages (
	ticket_id UUID NOT NULL, 
	sender_id UUID, 
	content TEXT NOT NULL, 
	is_internal BOOLEAN NOT NULL, 
	is_from_customer BOOLEAN NOT NULL, 
	attachment_url TEXT, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_ticket_messages PRIMARY KEY (id), 
	CONSTRAINT fk_ticket_messages_ticket_id_support_tickets FOREIGN KEY(ticket_id) REFERENCES support_tickets (id) ON DELETE CASCADE, 
	CONSTRAINT fk_ticket_messages_sender_id_users FOREIGN KEY(sender_id) REFERENCES users (id) ON DELETE SET NULL
);
""")

    op.execute("""
CREATE TABLE message_attachments (
	message_id UUID NOT NULL, 
	file_name VARCHAR(255) NOT NULL, 
	file_url TEXT NOT NULL, 
	file_type VARCHAR(100) NOT NULL, 
	file_size INTEGER, 
	whatsapp_media_id VARCHAR(255), 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_message_attachments PRIMARY KEY (id), 
	CONSTRAINT fk_message_attachments_message_id_conversation_messages FOREIGN KEY(message_id) REFERENCES conversation_messages (id) ON DELETE CASCADE
);
""")

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.execute("""CREATE INDEX ix_lead_stages_id ON lead_stages (id)""")
    op.execute("""CREATE INDEX ix_permissions_resource ON permissions (resource)""")
    op.execute("""CREATE INDEX ix_permissions_resource_action ON permissions (resource, action)""")
    op.execute("""CREATE INDEX ix_permissions_id ON permissions (id)""")
    op.execute("""CREATE UNIQUE INDEX ix_permissions_name ON permissions (name)""")
    op.execute("""CREATE UNIQUE INDEX ix_permissions_codename ON permissions (codename)""")
    op.execute("""CREATE INDEX ix_products_name ON products (name)""")
    op.execute("""CREATE INDEX ix_products_id ON products (id)""")
    op.execute("""CREATE INDEX ix_products_status ON products (status)""")
    op.execute("""CREATE INDEX ix_products_category ON products (category)""")
    op.execute("""CREATE INDEX ix_roles_id ON roles (id)""")
    op.execute("""CREATE UNIQUE INDEX ix_roles_name ON roles (name)""")
    op.execute("""CREATE INDEX ix_tags_entity_type ON tags (entity_type)""")
    op.execute("""CREATE INDEX ix_tags_id ON tags (id)""")
    op.execute("""CREATE UNIQUE INDEX ix_tags_name ON tags (name)""")
    op.execute("""CREATE INDEX ix_users_id ON users (id)""")
    op.execute("""CREATE UNIQUE INDEX ix_users_email ON users (email)""")
    op.execute("""CREATE UNIQUE INDEX ix_users_username ON users (username)""")
    op.execute("""CREATE INDEX ix_whatsapp_templates_id ON whatsapp_templates (id)""")
    op.execute("""CREATE UNIQUE INDEX ix_whatsapp_templates_name ON whatsapp_templates (name)""")
    op.execute("""CREATE INDEX ix_calendar_credentials_id ON calendar_credentials (id)""")
    op.execute("""CREATE UNIQUE INDEX ix_calendar_credentials_user_id ON calendar_credentials (user_id)""")
    op.execute("""CREATE INDEX ix_campaigns_scheduled_at ON campaigns (scheduled_at)""")
    op.execute("""CREATE INDEX ix_campaigns_status ON campaigns (status)""")
    op.execute("""CREATE INDEX ix_campaigns_name ON campaigns (name)""")
    op.execute("""CREATE INDEX ix_campaigns_id ON campaigns (id)""")
    op.execute("""CREATE INDEX ix_companies_id ON companies (id)""")
    op.execute("""CREATE INDEX ix_companies_name_industry ON companies (name, industry)""")
    op.execute("""CREATE INDEX ix_companies_name ON companies (name)""")
    op.execute("""CREATE INDEX ix_knowledge_documents_id ON knowledge_documents (id)""")
    op.execute("""CREATE INDEX ix_knowledge_documents_status ON knowledge_documents (status)""")
    op.execute("""CREATE INDEX ix_notifications_user_read ON notifications (user_id, is_read)""")
    op.execute("""CREATE INDEX ix_notifications_is_read ON notifications (is_read)""")
    op.execute("""CREATE INDEX ix_notifications_user_id ON notifications (user_id)""")
    op.execute("""CREATE INDEX ix_notifications_id ON notifications (id)""")
    op.execute("""CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id)""")
    op.execute("""CREATE INDEX ix_refresh_tokens_id ON refresh_tokens (id)""")
    op.execute("""CREATE UNIQUE INDEX ix_refresh_tokens_token_hash ON refresh_tokens (token_hash)""")
    op.execute("""CREATE INDEX ix_customers_assigned_to ON customers (assigned_to)""")
    op.execute("""CREATE UNIQUE INDEX ix_customers_whatsapp_id ON customers (whatsapp_id)""")
    op.execute("""CREATE INDEX ix_customers_status ON customers (status)""")
    op.execute("""CREATE INDEX ix_customers_company_id ON customers (company_id)""")
    op.execute("""CREATE INDEX ix_customers_name ON customers (first_name, last_name)""")
    op.execute("""CREATE INDEX ix_customers_email ON customers (email)""")
    op.execute("""CREATE INDEX ix_customers_status_assigned ON customers (status, assigned_to)""")
    op.execute("""CREATE INDEX ix_customers_phone ON customers (phone)""")
    op.execute("""CREATE INDEX ix_customers_id ON customers (id)""")
    op.execute("""CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id)""")
    op.execute("""CREATE INDEX ix_document_chunks_id ON document_chunks (id)""")
    op.execute("""CREATE INDEX ix_document_chunks_doc_idx ON document_chunks (document_id, chunk_index)""")
    op.execute("""CREATE INDEX ix_activities_customer_type ON activities (customer_id, activity_type)""")
    op.execute("""CREATE INDEX ix_activities_customer_id ON activities (customer_id)""")
    op.execute("""CREATE INDEX ix_activities_id ON activities (id)""")
    op.execute("""CREATE INDEX ix_activities_activity_type ON activities (activity_type)""")
    op.execute("""CREATE INDEX ix_appointments_start_time ON appointments (start_time)""")
    op.execute("""CREATE INDEX ix_appointments_start_status ON appointments (start_time, status)""")
    op.execute("""CREATE INDEX ix_appointments_assigned_to ON appointments (assigned_to)""")
    op.execute("""CREATE INDEX ix_appointments_status ON appointments (status)""")
    op.execute("""CREATE INDEX ix_appointments_id ON appointments (id)""")
    op.execute("""CREATE INDEX ix_appointments_customer_id ON appointments (customer_id)""")
    op.execute("""CREATE INDEX ix_campaign_recipients_campaign_status ON campaign_recipients (campaign_id, status)""")
    op.execute("""CREATE INDEX ix_campaign_recipients_campaign_id ON campaign_recipients (campaign_id)""")
    op.execute("""CREATE INDEX ix_campaign_recipients_customer_id ON campaign_recipients (customer_id)""")
    op.execute("""CREATE INDEX ix_campaign_recipients_status ON campaign_recipients (status)""")
    op.execute("""CREATE INDEX ix_campaign_recipients_id ON campaign_recipients (id)""")
    op.execute("""CREATE INDEX ix_conversations_phone_number ON conversations (phone_number)""")
    op.execute("""CREATE INDEX ix_conversations_status ON conversations (status)""")
    op.execute("""CREATE INDEX ix_conversations_id ON conversations (id)""")
    op.execute("""CREATE INDEX ix_conversations_customer_id ON conversations (customer_id)""")
    op.execute("""CREATE INDEX ix_conversations_assigned_to ON conversations (assigned_to)""")
    op.execute("""CREATE INDEX ix_conversations_customer_status ON conversations (customer_id, status)""")
    op.execute("""CREATE INDEX ix_conversations_whatsapp_conversation_id ON conversations (whatsapp_conversation_id)""")
    op.execute("""CREATE INDEX ix_conversations_last_message_at ON conversations (last_message_at)""")
    op.execute("""CREATE INDEX ix_leads_id ON leads (id)""")
    op.execute("""CREATE INDEX ix_leads_assigned_to ON leads (assigned_to)""")
    op.execute("""CREATE INDEX ix_leads_customer_id ON leads (customer_id)""")
    op.execute("""CREATE INDEX ix_leads_status_assigned ON leads (status, assigned_to)""")
    op.execute("""CREATE INDEX ix_leads_status ON leads (status)""")
    op.execute("""CREATE INDEX ix_orders_id ON orders (id)""")
    op.execute("""CREATE INDEX ix_orders_status ON orders (status)""")
    op.execute("""CREATE UNIQUE INDEX ix_orders_order_number ON orders (order_number)""")
    op.execute("""CREATE INDEX ix_orders_customer_id ON orders (customer_id)""")
    op.execute("""CREATE INDEX ix_orders_customer_status ON orders (customer_id, status)""")
    op.execute("""CREATE INDEX ix_tickets_customer_status ON support_tickets (customer_id, status)""")
    op.execute("""CREATE UNIQUE INDEX ix_support_tickets_ticket_number ON support_tickets (ticket_number)""")
    op.execute("""CREATE INDEX ix_support_tickets_customer_id ON support_tickets (customer_id)""")
    op.execute("""CREATE INDEX ix_support_tickets_status ON support_tickets (status)""")
    op.execute("""CREATE INDEX ix_support_tickets_assigned_to ON support_tickets (assigned_to)""")
    op.execute("""CREATE INDEX ix_support_tickets_id ON support_tickets (id)""")
    op.execute("""CREATE INDEX ix_conv_messages_conv_direction ON conversation_messages (conversation_id, direction)""")
    op.execute("""CREATE INDEX ix_conversation_messages_direction ON conversation_messages (direction)""")
    op.execute("""CREATE INDEX ix_conversation_messages_conversation_id ON conversation_messages (conversation_id)""")
    op.execute("""CREATE INDEX ix_conversation_messages_id ON conversation_messages (id)""")
    op.execute("""CREATE UNIQUE INDEX ix_conversation_messages_whatsapp_message_id ON conversation_messages (whatsapp_message_id)""")
    op.execute("""CREATE INDEX ix_conversation_summaries_customer_id ON conversation_summaries (customer_id)""")
    op.execute("""CREATE UNIQUE INDEX ix_conversation_summaries_conversation_id ON conversation_summaries (conversation_id)""")
    op.execute("""CREATE INDEX ix_conversation_summaries_id ON conversation_summaries (id)""")
    op.execute("""CREATE INDEX ix_follow_ups_status ON follow_ups (status)""")
    op.execute("""CREATE INDEX ix_follow_ups_id ON follow_ups (id)""")
    op.execute("""CREATE INDEX ix_followups_scheduled_status ON follow_ups (scheduled_at, status)""")
    op.execute("""CREATE INDEX ix_follow_ups_scheduled_at ON follow_ups (scheduled_at)""")
    op.execute("""CREATE INDEX ix_follow_ups_customer_id ON follow_ups (customer_id)""")
    op.execute("""CREATE INDEX ix_notes_id ON notes (id)""")
    op.execute("""CREATE INDEX ix_notes_lead_id ON notes (lead_id)""")
    op.execute("""CREATE INDEX ix_notes_customer_id ON notes (customer_id)""")
    op.execute("""CREATE INDEX ix_order_items_id ON order_items (id)""")
    op.execute("""CREATE INDEX ix_order_items_order_id ON order_items (order_id)""")
    op.execute("""CREATE INDEX ix_payments_transaction_id ON payments (transaction_id)""")
    op.execute("""CREATE INDEX ix_payments_id ON payments (id)""")
    op.execute("""CREATE INDEX ix_payments_order_id ON payments (order_id)""")
    op.execute("""CREATE INDEX ix_tasks_customer_id ON tasks (customer_id)""")
    op.execute("""CREATE INDEX ix_tasks_assigned_status ON tasks (assigned_to, status)""")
    op.execute("""CREATE INDEX ix_tasks_assigned_to ON tasks (assigned_to)""")
    op.execute("""CREATE INDEX ix_tasks_id ON tasks (id)""")
    op.execute("""CREATE INDEX ix_tasks_due_date ON tasks (due_date)""")
    op.execute("""CREATE INDEX ix_tasks_status ON tasks (status)""")
    op.execute("""CREATE INDEX ix_ticket_messages_ticket_id ON ticket_messages (ticket_id)""")
    op.execute("""CREATE INDEX ix_ticket_messages_id ON ticket_messages (id)""")
    op.execute("""CREATE INDEX ix_message_attachments_id ON message_attachments (id)""")
    op.execute("""CREATE INDEX ix_message_attachments_message_id ON message_attachments (message_id)""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS message_attachments CASCADE")
    op.execute("DROP TABLE IF EXISTS ticket_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS payments CASCADE")
    op.execute("DROP TABLE IF EXISTS order_items CASCADE")
    op.execute("DROP TABLE IF EXISTS notes CASCADE")
    op.execute("DROP TABLE IF EXISTS follow_ups CASCADE")
    op.execute("DROP TABLE IF EXISTS conversation_summaries CASCADE")
    op.execute("DROP TABLE IF EXISTS conversation_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS support_tickets CASCADE")
    op.execute("DROP TABLE IF EXISTS orders CASCADE")
    op.execute("DROP TABLE IF EXISTS leads CASCADE")
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")
    op.execute("DROP TABLE IF EXISTS campaign_recipients CASCADE")
    op.execute("DROP TABLE IF EXISTS appointments CASCADE")
    op.execute("DROP TABLE IF EXISTS activities CASCADE")
    op.execute("DROP TABLE IF EXISTS document_chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS customers CASCADE")
    op.execute("DROP TABLE IF EXISTS user_roles CASCADE")
    op.execute("DROP TABLE IF EXISTS role_permissions CASCADE")
    op.execute("DROP TABLE IF EXISTS refresh_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS knowledge_documents CASCADE")
    op.execute("DROP TABLE IF EXISTS companies CASCADE")
    op.execute("DROP TABLE IF EXISTS campaigns CASCADE")
    op.execute("DROP TABLE IF EXISTS calendar_credentials CASCADE")
    op.execute("DROP TABLE IF EXISTS whatsapp_templates CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS tags CASCADE")
    op.execute("DROP TABLE IF EXISTS roles CASCADE")
    op.execute("DROP TABLE IF EXISTS products CASCADE")
    op.execute("DROP TABLE IF EXISTS permissions CASCADE")
    op.execute("DROP TABLE IF EXISTS lead_stages CASCADE")

    op.execute("DROP TYPE IF EXISTS productstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS templatestatus CASCADE")
    op.execute("DROP TYPE IF EXISTS campaigntype CASCADE")
    op.execute("DROP TYPE IF EXISTS campaignstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS companysize CASCADE")
    op.execute("DROP TYPE IF EXISTS documentstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS notificationtype CASCADE")
    op.execute("DROP TYPE IF EXISTS customergender CASCADE")
    op.execute("DROP TYPE IF EXISTS customerstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS activitytype CASCADE")
    op.execute("DROP TYPE IF EXISTS appointmenttype CASCADE")
    op.execute("DROP TYPE IF EXISTS appointmentstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS recipientstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS conversationstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS leadstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS leadpriority CASCADE")
    op.execute("DROP TYPE IF EXISTS leadsource CASCADE")
    op.execute("DROP TYPE IF EXISTS orderstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS paymentstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS ticketstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS ticketpriority CASCADE")
    op.execute("DROP TYPE IF EXISTS messagedirection CASCADE")
    op.execute("DROP TYPE IF EXISTS messagetype CASCADE")
    op.execute("DROP TYPE IF EXISTS followuptype CASCADE")
    op.execute("DROP TYPE IF EXISTS followupstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS taskstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS taskpriority CASCADE")
