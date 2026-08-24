"use client";

import { useEffect, useState } from "react";
import apiClient, { getErrorMessage } from "@/lib/api";
import { Appointment, User } from "@/types";
import { toast } from "sonner";
import { format } from "date-fns";

export default function AdminDashboard() {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAppointments();
  }, []);

  const fetchAppointments = async () => {
    try {
      const res = await apiClient.get<{ data: Appointment[] }>("/appointments/my");
      setAppointments(res.data.data);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div className="px-4 py-6 sm:px-0">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Admin Dashboard</h1>
        <p className="mb-8 text-gray-600">Overview of all system appointments.</p>

        {loading ? (
          <div className="flex justify-center p-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          </div>
        ) : appointments.length === 0 ? (
          <div className="bg-white overflow-hidden shadow rounded-lg text-center p-12">
            <h3 className="mt-2 text-sm font-medium text-gray-900">No appointments in the system</h3>
          </div>
        ) : (
          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul role="list" className="divide-y divide-gray-200">
              {appointments.map((appt) => (
                <li key={appt.id}>
                  <div className="px-4 py-4 sm:px-6">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium text-indigo-600 truncate">
                        ID: {appt.id.substring(0, 8)}... | Patient: {appt.patient_id.substring(0, 8)}... | Doctor: {appt.doctor_id.substring(0, 8)}...
                      </p>
                      <div className="ml-2 flex-shrink-0 flex">
                        <p className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                          ${appt.status === 'CONFIRMED' ? 'bg-green-100 text-green-800' : 
                            appt.status === 'COMPLETED' ? 'bg-blue-100 text-blue-800' : 
                            appt.status === 'CANCELLED' ? 'bg-red-100 text-red-800' : 
                            'bg-gray-100 text-gray-800'}`}>
                          {appt.status}
                        </p>
                      </div>
                    </div>
                    <div className="mt-2 sm:flex sm:justify-between">
                      <div className="sm:flex">
                        <p className="flex items-center text-sm text-gray-500">
                          Started: {format(new Date(appt.start_time), "MMM d, yyyy h:mm a")}
                        </p>
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </main>
  );
}
