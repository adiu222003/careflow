/**
 * Shared TypeScript types for the CareFlow frontend.
 * Mirrors the Pydantic schemas from the backend.
 */

// ── Auth ─────────────────────────────────────────────────────────────────────
export type Role = "PATIENT" | "DOCTOR" | "ADMIN";

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface TokenData {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  token: TokenData;
  user: User;
}

// ── Doctor ────────────────────────────────────────────────────────────────────
export type DayOfWeek = 0 | 1 | 2 | 3 | 4 | 5 | 6;

export interface DoctorProfile {
  id: string;
  user_id: string;
  specialisation: string;
  bio: string | null;
  consultation_fee: number | null;
  slot_duration_minutes: number;
  timezone: string;
  user: User;
  working_hours: WorkingHours[];
}

export interface WorkingHours {
  id: string;
  day_of_week: DayOfWeek;
  start_time: string; // "HH:MM"
  end_time: string;
  is_working: boolean;
}

export interface DoctorLeave {
  id: string;
  doctor_id: string;
  leave_date: string; // "YYYY-MM-DD"
  reason: string | null;
}

// ── Appointments ──────────────────────────────────────────────────────────────
export type AppointmentStatus = "CONFIRMED" | "COMPLETED" | "CANCELLED";
export type HoldStatus = "HELD" | "EXPIRED" | "CONVERTED";
export type UrgencyLevel = "Low" | "Medium" | "High";
export type AIStatus = "PENDING" | "SUCCESS" | "FAILED";

export interface AppointmentHold {
  id: string;
  doctor_id: string;
  patient_id: string;
  start_time: string;
  end_time: string;
  expires_at: string;
  status: HoldStatus;
}

export interface Appointment {
  id: string;
  doctor_id: string;
  patient_id: string;
  booking_reference: string;
  start_time: string;
  end_time: string;
  status: AppointmentStatus;
  symptoms: string | null;
  pre_visit_summary: string | null;
  urgency_level: UrgencyLevel | null;
  pre_visit_ai_status: AIStatus;
  doctor_notes: string | null;
  post_visit_summary: string | null;
  post_visit_ai_status: AIStatus;
  cancellation_reason: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
  doctor?: DoctorProfile;
  patient?: User;
}

// ── Prescription ──────────────────────────────────────────────────────────────
export interface PrescriptionItem {
  id: string;
  medicine_name: string;
  dosage: string;
  frequency: string;
  duration_days: number | null;
  instructions: string | null;
}

export interface Prescription {
  id: string;
  appointment_id: string;
  notes: string | null;
  created_at: string;
  items: PrescriptionItem[];
}

// ── API Response wrappers ─────────────────────────────────────────────────────
export interface ApiSuccess<T> {
  success: true;
  data: T;
}

export interface ApiError {
  success: false;
  error: {
    code: string;
    message: string;
  };
}

export type ApiResponse<T> = ApiSuccess<T> | ApiError;

export interface PaginatedResponse<T> {
  success: true;
  data: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

// ── Availability ──────────────────────────────────────────────────────────────
export interface TimeSlot {
  start_time: string;
  end_time: string;
  available: boolean;
}
