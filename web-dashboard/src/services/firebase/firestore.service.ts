// src/services/firebase/firestore.service.ts
import {
  getFirestore,
  collection,
  doc,
  setDoc,
  getDoc,
  getDocs,
  query,
  where,
  orderBy,
  limit,
  startAfter,
  QueryConstraint,
  QueryDocumentSnapshot,
  DocumentData,
  updateDoc,
  deleteDoc,
  Timestamp,
} from 'firebase/firestore';
import { app } from '@/firebase';

const db = getFirestore(app);

export interface AttendanceRecord {
  id: string;
  student_id: string;
  student_name: string;
  course_id: string;
  course_name: string;
  marked_at: Timestamp;
  status: 'present' | 'late' | 'absent' | 'excused';
  confidence?: number;
  avatar_url?: string;
}

export interface Student {
  id: string;
  name: string;
  email: string;
  student_id: string;
  avatar_url?: string;
  created_at: Timestamp;
}

export interface Course {
  id: string;
  name: string;
  code: string;
  instructor: string;
  created_at: Timestamp;
}

/**
 * Add a new document
 */
export const addDocument = async (
  collectionName: string,
  data: any
): Promise<string> => {
  try {
    const docRef = doc(collection(db, collectionName));
    await setDoc(docRef, {
      ...data,
      created_at: Timestamp.now(),
    });
    return docRef.id;
  } catch (error: any) {
    console.error(`Error adding document to ${collectionName}:`, error);
    throw error;
  }
};

/**
 * Get a single document by ID
 */
export const getDocument = async (
  collectionName: string,
  docId: string
): Promise<any> => {
  try {
    const docRef = doc(db, collectionName, docId);
    const docSnap = await getDoc(docRef);
    if (docSnap.exists()) {
      return { id: docSnap.id, ...docSnap.data() };
    } else {
      return null;
    }
  } catch (error: any) {
    console.error(`Error getting document from ${collectionName}:`, error);
    throw error;
  }
};

/**
 * Query documents with constraints
 */
export const queryDocuments = async (
  collectionName: string,
  constraints: QueryConstraint[]
): Promise<any[]> => {
  try {
    const q = query(collection(db, collectionName), ...constraints);
    const querySnapshot = await getDocs(q);
    return querySnapshot.docs.map((doc) => ({
      id: doc.id,
      ...doc.data(),
    }));
  } catch (error: any) {
    console.error(`Error querying ${collectionName}:`, error);
    throw error;
  }
};

/**
 * Get all documents from a collection
 */
export const getAllDocuments = async (collectionName: string): Promise<any[]> => {
  try {
    const querySnapshot = await getDocs(collection(db, collectionName));
    return querySnapshot.docs.map((doc) => ({
      id: doc.id,
      ...doc.data(),
    }));
  } catch (error: any) {
    console.error(`Error getting all documents from ${collectionName}:`, error);
    throw error;
  }
};

/**
 * Update a document
 */
export const updateDocument = async (
  collectionName: string,
  docId: string,
  data: any
): Promise<void> => {
  try {
    const docRef = doc(db, collectionName, docId);
    await updateDoc(docRef, {
      ...data,
      updated_at: Timestamp.now(),
    });
  } catch (error: any) {
    console.error(`Error updating document in ${collectionName}:`, error);
    throw error;
  }
};

/**
 * Delete a document
 */
export const deleteDocument = async (
  collectionName: string,
  docId: string
): Promise<void> => {
  try {
    const docRef = doc(db, collectionName, docId);
    await deleteDoc(docRef);
  } catch (error: any) {
    console.error(`Error deleting document from ${collectionName}:`, error);
    throw error;
  }
};

/**
 * Get attendance records for a student
 */
export const getStudentAttendance = async (
  studentId: string,
  limitNum: number = 100
): Promise<AttendanceRecord[]> => {
  try {
    const constraints: QueryConstraint[] = [
      where('student_id', '==', studentId),
      orderBy('marked_at', 'desc'),
      limit(limitNum),
    ];
    return queryDocuments('attendance', constraints);
  } catch (error: any) {
    console.error('Error getting student attendance:', error);
    throw error;
  }
};

/**
 * Get attendance records for a course
 */
export const getCourseAttendance = async (
  courseId: string,
  limitNum: number = 100
): Promise<AttendanceRecord[]> => {
  try {
    const constraints: QueryConstraint[] = [
      where('course_id', '==', courseId),
      orderBy('marked_at', 'desc'),
      limit(limitNum),
    ];
    return queryDocuments('attendance', constraints);
  } catch (error: any) {
    console.error('Error getting course attendance:', error);
    throw error;
  }
};

/**
 * Get all students
 */
export const getAllStudents = async (): Promise<Student[]> => {
  try {
    return getAllDocuments('students');
  } catch (error: any) {
    console.error('Error getting students:', error);
    throw error;
  }
};

/**
 * Get all courses
 */
export const getAllCourses = async (): Promise<Course[]> => {
  try {
    return getAllDocuments('courses');
  } catch (error: any) {
    console.error('Error getting courses:', error);
    throw error;
  }
};

export default db;
