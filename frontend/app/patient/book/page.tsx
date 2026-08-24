"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DoctorProfile, TimeSlot, AppointmentHold } from "@/types";
import apiClient, { getErrorMessage } from "@/lib/api";

export default function BookAppointmentPage() {
  const router = useRouter();
  const [doctors, setDoctors] = useState<DoctorProfile[]>([]);
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("");
  const [date, setDate] = useState<string>(new Date().toISOString().split("T")[0]);
  const [slots, setSlots] = useState<TimeSlot[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null);
  const [symptoms, setSymptoms] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hold, setHold] = useState<AppointmentHold | null>(null);

  // 1. Load doctors
  useEffect(() => {
    const loadDoctors = async () => {
      try {
        const { data } = await apiClient.get("/doctors");
        if (data.success) {
          setDoctors(data.data);
        }
      } catch (err) {
        console.error(err);
      }
    };
    loadDoctors();
  }, []);

  // 2. Load slots when doctor and date change
  useEffect(() => {
    const loadSlots = async () => {
      if (!selectedDoctorId || !date) {
        setSlots([]);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const { data } = await apiClient.get(
          `/doctors/${selectedDoctorId}/availability`,
          { params: { start_date: date, end_date: date } }
        );
        if (data.success) {
          setSlots(data.data);
        }
      } catch (err: any) {
        setError(getErrorMessage(err));
      } finally {
        setLoading(false);
      }
    };
    loadSlots();
  }, [selectedDoctorId, date]);

  // 3. Create Hold
  const handleHold = async (slot: TimeSlot) => {
    setError(null);
    setLoading(true);
    try {
      const { data } = await apiClient.post("/appointments/hold", {
        doctor_id: selectedDoctorId,
        start_time: slot.start_time,
        end_time: slot.end_time,
      });
      if (data.success) {
        setHold(data.data);
        setSelectedSlot(slot);
      }
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  // 4. Confirm Booking
  const handleBook = async () => {
    if (!hold || !symptoms.trim()) {
      setError("Symptoms are required");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const { data } = await apiClient.post("/appointments/book", {
        hold_id: hold.id,
        symptoms,
      });
      if (data.success) {
        router.push("/patient/dashboard");
      }
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  if (hold && selectedSlot) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <h1 className="text-2xl font-bold mb-6">Confirm Appointment</h1>
        {error && <div className="p-4 mb-4 text-red-700 bg-red-100 rounded-lg">{error}</div>}
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="font-semibold mb-2">Slot Reserved!</h2>
          <p className="text-gray-600 mb-4">
            {new Date(selectedSlot.start_time).toLocaleString()} - {new Date(selectedSlot.end_time).toLocaleTimeString()}
          </p>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              What are your symptoms or reason for visit?
            </label>
            <textarea
              className="w-full p-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
              rows={4}
              value={symptoms}
              onChange={(e) => setSymptoms(e.target.value)}
              placeholder="E.g., I have been experiencing mild chest pain..."
            />
          </div>
          <button
            onClick={handleBook}
            disabled={loading}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
          >
            {loading ? "Booking..." : "Confirm Booking"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-8">
      <h1 className="text-2xl font-bold mb-6">Book an Appointment</h1>
      
      {error && <div className="p-4 mb-6 text-red-700 bg-red-100 rounded-lg">{error}</div>}

      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Select Doctor</label>
            <select
              className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
              value={selectedDoctorId}
              onChange={(e) => setSelectedDoctorId(e.target.value)}
            >
              <option value="">-- Choose a Doctor --</option>
              {doctors.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.user.full_name} ({doc.specialisation})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Date</label>
            <input
              type="date"
              className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
              value={date}
              min={new Date().toISOString().split("T")[0]}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
        </div>
      </div>

      {selectedDoctorId && date && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Available Slots</h2>
          {loading ? (
            <p className="text-gray-500">Loading slots...</p>
          ) : slots.length === 0 ? (
            <p className="text-gray-500">No available slots on this date.</p>
          ) : (
            <div className="grid grid-cols-3 gap-4 sm:grid-cols-4 md:grid-cols-5">
              {slots.map((slot, i) => (
                <button
                  key={i}
                  disabled={!slot.available}
                  onClick={() => handleHold(slot)}
                  className={`
                    px-4 py-2 text-sm font-medium rounded-md border
                    ${
                      slot.available
                        ? "bg-white border-indigo-600 text-indigo-600 hover:bg-indigo-50 cursor-pointer"
                        : "bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed opacity-50"
                    }
                  `}
                >
                  {new Date(slot.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
