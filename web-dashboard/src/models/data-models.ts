export interface StudentModel {
  id: string;
  name: string;
  email: string;
  photoUrl?: string;
  studentId: string;
  courseId: string;
  createdAt: Date;
}

export interface AttendanceModel {
  id: string;
  studentId: string;
  courseId: string;
  isPresent: boolean;
  timestamp: Date;
  photoUrl?: string;
}

export interface StatisticsModel {
  totalStudents: number;
  presentCount: number;
  absentCount: number;
  attendancePercentage: number;
}

export interface CourseModel {
  id: string;
  name: string;
  code: string;
  instructor: string;
  createdAt: Date;
}

export class StudentDTO implements StudentModel {
  id!: string;
  name!: string;
  email!: string;
  photoUrl?: string;
  studentId!: string;
  courseId!: string;
  createdAt!: Date;

  static fromJSON(json: any): StudentDTO {
    const student = new StudentDTO();
    student.id = json.id || '';
    student.name = json.name || '';
    student.email = json.email || '';
    student.photoUrl = json.photo_url;
    student.studentId = json.student_id || '';
    student.courseId = json.course_id || '';
    student.createdAt = json.created_at
      ? new Date(json.created_at)
      : new Date();
    return student;
  }

  toJSON(): any {
    return {
      id: this.id,
      name: this.name,
      email: this.email,
      photo_url: this.photoUrl,
      student_id: this.studentId,
      course_id: this.courseId,
      created_at: this.createdAt.toISOString(),
    };
  }
}

export class AttendanceDTO implements AttendanceModel {
  id!: string;
  studentId!: string;
  courseId!: string;
  isPresent!: boolean;
  timestamp!: Date;
  photoUrl?: string;

  static fromJSON(json: any): AttendanceDTO {
    const attendance = new AttendanceDTO();
    attendance.id = json.id || '';
    attendance.studentId = json.student_id || '';
    attendance.courseId = json.course_id || '';
    attendance.isPresent = json.is_present || false;
    attendance.timestamp = json.timestamp
      ? new Date(json.timestamp)
      : new Date();
    attendance.photoUrl = json.photo_url;
    return attendance;
  }

  toJSON(): any {
    return {
      id: this.id,
      student_id: this.studentId,
      course_id: this.courseId,
      is_present: this.isPresent,
      timestamp: this.timestamp.toISOString(),
      photo_url: this.photoUrl,
    };
  }
}

export class StatisticsDTO implements StatisticsModel {
  totalStudents!: number;
  presentCount!: number;
  absentCount!: number;
  attendancePercentage!: number;

  static fromJSON(json: any): StatisticsDTO {
    const stats = new StatisticsDTO();
    stats.totalStudents = json.total_students || 0;
    stats.presentCount = json.present_count || 0;
    stats.absentCount = json.absent_count || 0;
    stats.attendancePercentage =
      json.attendance_percentage || 0;
    return stats;
  }

  toJSON(): any {
    return {
      total_students: this.totalStudents,
      present_count: this.presentCount,
      absent_count: this.absentCount,
      attendance_percentage: this.attendancePercentage,
    };
  }
}
