-- Run this in Supabase SQL Editor to create the review_cards table

CREATE TABLE review_cards (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  review_id TEXT UNIQUE NOT NULL,
  reviewer_name TEXT NOT NULL,
  star_rating INTEGER NOT NULL,
  review_text TEXT,
  gbp_location TEXT,
  hubspot_contact_id TEXT,
  contact_address JSONB,
  handwrytten_order_id TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  -- status values: pending, matched, no_match, no_address, sent, failed
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  sent_at TIMESTAMPTZ
);

-- Index for fast status lookups
CREATE INDEX idx_review_cards_status ON review_cards(status);

-- Index for duplicate check
CREATE INDEX idx_review_cards_review_id ON review_cards(review_id);
