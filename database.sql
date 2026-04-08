-- Users & Authentication
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL, -- 'customer', 'driver', 'admin'
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    profile_photo_url TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Driver-specific details
CREATE TABLE drivers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    license_number VARCHAR(100) UNIQUE NOT NULL,
    license_state VARCHAR(2),
    license_expiry DATE,
    insurance_policy_number VARCHAR(100),
    insurance_expiry DATE,
    background_check_status VARCHAR(20), -- 'pending', 'approved', 'rejected'
    background_check_date DATE,
    company_name VARCHAR(255),
    company_ein VARCHAR(20),
    bank_account_id VARCHAR(255), -- Stripe Connect account ID
    commission_rate DECIMAL(5,2) DEFAULT 15.00, -- Platform fee percentage
    rating DECIMAL(3,2) DEFAULT 5.00,
    total_tows INTEGER DEFAULT 0,
    is_online BOOLEAN DEFAULT FALSE,
    current_location GEOGRAPHY(POINT),
    approval_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'suspended'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Tow trucks
CREATE TABLE vehicles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    driver_id UUID REFERENCES drivers(id) ON DELETE CASCADE,
    vehicle_type VARCHAR(50) NOT NULL, -- 'flatbed', 'wheel_lift', 'integrated', 'hook_chain'
    make VARCHAR(100),
    model VARCHAR(100),
    year INTEGER,
    license_plate VARCHAR(20),
    vin VARCHAR(50),
    insurance_policy VARCHAR(100),
    capacity_weight INTEGER, -- in pounds
    can_tow_types TEXT[], -- ['sedan', 'suv', 'truck', 'motorcycle', 'van']
    photos TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tow service types & pricing
CREATE TABLE service_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL, -- 'Standard Tow', 'Flatbed Tow', 'Motorcycle Tow', etc.
    description TEXT,
    base_price DECIMAL(10,2), -- Base price for first X miles
    per_mile_rate DECIMAL(10,2), -- Rate per mile after base
    included_miles INTEGER DEFAULT 5, -- Miles included in base price
    is_active BOOLEAN DEFAULT TRUE
);

-- Vehicle categories for customers
CREATE TABLE customer_vehicle_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL, -- 'Sedan', 'SUV', 'Truck', 'Motorcycle', 'Van', 'RV'
    price_multiplier DECIMAL(3,2) DEFAULT 1.00, -- Multiplier on base price
    description TEXT
);

-- Tow reasons
CREATE TABLE tow_reasons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL, -- 'Breakdown', 'Accident', 'Flat Tire', 'Dead Battery', 'Out of Fuel', 'Lockout', 'Impound'
    requires_flatbed BOOLEAN DEFAULT FALSE,
    price_adjustment DECIMAL(10,2) DEFAULT 0.00, -- Additional fee for certain reasons
    description TEXT
);

-- Tow requests
CREATE TABLE tow_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES users(id),
    driver_id UUID REFERENCES drivers(id),
    service_type_id UUID REFERENCES service_types(id),
    vehicle_type_id UUID REFERENCES customer_vehicle_types(id),
    tow_reason_id UUID REFERENCES tow_reasons(id),
    
    -- Location details
    pickup_location GEOGRAPHY(POINT) NOT NULL,
    pickup_address TEXT NOT NULL,
    pickup_notes TEXT,
    dropoff_location GEOGRAPHY(POINT) NOT NULL,
    dropoff_address TEXT NOT NULL,
    dropoff_notes TEXT,
    distance_miles DECIMAL(10,2),
    
    -- Vehicle details
    vehicle_make VARCHAR(100),
    vehicle_model VARCHAR(100),
    vehicle_year INTEGER,
    vehicle_color VARCHAR(50),
    license_plate VARCHAR(20),
    
    -- Pricing
    quoted_price DECIMAL(10,2), -- What customer sees/pays
    driver_payout DECIMAL(10,2), -- What driver receives
    platform_fee DECIMAL(10,2), -- Your commission
    stripe_fee DECIMAL(10,2),
    
    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending', 
    -- 'pending' -> 'searching' -> 'accepted' -> 'en_route_pickup' -> 'arrived_pickup' 
    -- -> 'vehicle_loaded' -> 'en_route_dropoff' -> 'arrived_dropoff' -> 'completed' -> 'cancelled'
    
    requested_at TIMESTAMP DEFAULT NOW(),
    accepted_at TIMESTAMP,
    arrived_pickup_at TIMESTAMP,
    loaded_at TIMESTAMP,
    arrived_dropoff_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    cancellation_reason TEXT,
    
    -- Payment
    payment_intent_id VARCHAR(255), -- Stripe PaymentIntent ID
    payment_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'authorized', 'captured', 'refunded'
    
    -- Rating
    customer_rating INTEGER, -- 1-5
    customer_review TEXT,
    driver_rating INTEGER, -- 1-5
    driver_review TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Driver matching/rejection tracking
CREATE TABLE tow_request_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tow_request_id UUID REFERENCES tow_requests(id) ON DELETE CASCADE,
    driver_id UUID REFERENCES drivers(id),
    offered_at TIMESTAMP DEFAULT NOW(),
    response VARCHAR(20), -- 'pending', 'accepted', 'rejected', 'expired'
    responded_at TIMESTAMP,
    rejection_reason TEXT,
    distance_from_pickup DECIMAL(10,2) -- Miles from driver to pickup
);

-- Real-time location tracking during active tow
CREATE TABLE location_history (
    id BIGSERIAL PRIMARY KEY,
    tow_request_id UUID REFERENCES tow_requests(id) ON DELETE CASCADE,
    driver_id UUID REFERENCES drivers(id),
    location GEOGRAPHY(POINT) NOT NULL,
    speed DECIMAL(5,2), -- mph
    heading INTEGER, -- 0-359 degrees
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Transactions & payouts
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tow_request_id UUID REFERENCES tow_requests(id),
    customer_id UUID REFERENCES users(id),
    driver_id UUID REFERENCES drivers(id),
    
    amount DECIMAL(10,2) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL, -- 'charge', 'refund', 'payout', 'platform_fee'
    
    stripe_charge_id VARCHAR(255),
    stripe_transfer_id VARCHAR(255),
    stripe_refund_id VARCHAR(255),
    
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'completed', 'failed'
    description TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Support tickets
CREATE TABLE support_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    tow_request_id UUID REFERENCES tow_requests(id),
    subject VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'open', -- 'open', 'in_progress', 'resolved', 'closed'
    priority VARCHAR(20) DEFAULT 'normal', -- 'low', 'normal', 'high', 'urgent'
    assigned_to UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

-- Support messages
CREATE TABLE support_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID REFERENCES support_tickets(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Notifications
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    type VARCHAR(50), -- 'tow_request', 'tow_update', 'payment', 'promo', 'system'
    data JSONB, -- Additional metadata
    is_read BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP DEFAULT NOW()
);

-- Promo codes
CREATE TABLE promo_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    discount_type VARCHAR(20), -- 'percentage', 'fixed'
    discount_value DECIMAL(10,2),
    max_uses INTEGER,
    used_count INTEGER DEFAULT 0,
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_drivers_location ON drivers USING GIST(current_location);
CREATE INDEX idx_drivers_online ON drivers(is_online) WHERE is_online = TRUE;
CREATE INDEX idx_tow_requests_status ON tow_requests(status);
CREATE INDEX idx_tow_requests_customer ON tow_requests(customer_id);
CREATE INDEX idx_tow_requests_driver ON tow_requests(driver_id);
CREATE INDEX idx_tow_requests_created ON tow_requests(created_at DESC);
CREATE INDEX idx_location_history_request ON location_history(tow_request_id, recorded_at DESC);
CREATE INDEX idx_notifications_user ON notifications(user_id, is_read, sent_at DESC);
