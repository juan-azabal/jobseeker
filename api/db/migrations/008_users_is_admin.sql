-- Migration 008: add is_admin flag to users table for admin access control
ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0;
