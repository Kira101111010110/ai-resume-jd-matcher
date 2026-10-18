import { CreateMember, CreateResume, GetMemberByUserAndPost, GetMyApplicationResultModel, GetDataPostById, GetPostModel } from "../models/applicant.js"
import { GetTotalPage } from "../models/auth.js";
import AppError from '../utils/AppError.js'
import { UploadToCloudinary } from "../utils/UploadToCloudinary.js";
import axios from "axios"

// AI service: ตั้งบน Render (Environment)
//   AI_SERVICE_URL   = URL จากหน้าตั้งค่าของ exe (ไม่มี / ท้าย) — ไม่ตั้ง = ใช้ ngrok URL เดิม
//   AI_SERVICE_TOKEN = Token ลับจากหน้าตั้งค่าของ exe — ไม่ตั้ง = ไม่ส่ง header (ใช้กับ uvicorn + ngrok แบบเดิมได้)
const AI_SERVICE_URL = (process.env.AI_SERVICE_URL || "https://duckling-hangup-resistant.ngrok-free.dev").replace(/\/+$/, "")
const AI_SERVICE_TOKEN = process.env.AI_SERVICE_TOKEN
const AI_TIMEOUT_MS = 180000 // วิเคราะห์ปกติ 10–60 วินาที ไฟล์ที่ต้อง OCR อาจนานกว่านั้น

export const GetPostService = async (query = {}) => {
    let { page, limit, filter = null } = query
    const { search = null } = query

    page = Number(page)
    limit = Number(limit)

    page = page > 0 ? page : 1
    limit = limit < 11 && limit > 0 ? limit : 10
    const setoff = (page - 1) * limit
    const filteCheck = ['open', 'closed']

    if (!filteCheck.includes(filter) && filter !== null) {
        filter = null
    }

    const result = await GetPostModel(setoff, limit, search, filter)

    const total = await GetTotalPage('posts')
    const totalPages = Math.ceil(total.total/limit)

    let nextPage = page < totalPages ? page + 1 : null
    let prevPage = page > 1 ? page - 1 : null

    return {
        message : 'Get post succeed',
        data : result,
        meta : {
            total : total.total,
            page,
            limit,
            hasnextPage : page < totalPages,
            hasPrevPage : page > 1,
            nextPage,
            prevPage
        }
    }
}

const CallAiService = async (body) => {
    const headers = {}
    if (AI_SERVICE_TOKEN) headers["X-AI-Token"] = AI_SERVICE_TOKEN

    try {
        return await axios.post(`${AI_SERVICE_URL}/analyze`, body, { headers, timeout: AI_TIMEOUT_MS })
    } catch (err) {
        const status = err.response?.status
        console.error("AI service error:", status, err.response?.data || err.message)

        if (status === 401) {
            // AI_SERVICE_TOKEN ไม่ตรงกับในหน้าตั้งค่าของ exe
            throw new AppError("AI service authentication failed. Please contact the administrator.", 503)
        }
        if (!err.response || [404, 502, 503, 504].includes(status)) {
            // exe / uvicorn ปิดอยู่, ngrok หลุด หรือหมดเวลารอ
            throw new AppError("AI service is currently unavailable. Please try again later.", 503)
        }
        // 400/422/500 จาก AI: detail เป็นข้อความภาษาไทยที่บอกสาเหตุ (เช่น อ่าน PDF ไม่ได้, key ใช้ไม่ได้)
        const detail = typeof err.response.data?.detail === "string" ? err.response.data.detail : "AI analysis failed"
        throw new AppError(detail, status >= 500 ? 502 : 422)
    }
}

export const ApplyResumeService = async (
    userId,
    postId,
    files,
) => {

    const member = await GetMemberByUserAndPost(
        userId,
        postId
    );

    if (member) {
        throw new AppError("You already applied", 409);
    }

        const post = await GetDataPostById(postId)

    if (!post) {
        throw new AppError("Post not found", 404)
    }

    const resume = files.resume?.[0];
    const transcript = files.transcript?.[0];


    if (!resume || !transcript) {
        throw new AppError(
            "Please upload resume and transcript",
            400
        );
    }


    const resumeUpload = await UploadToCloudinary(
        resume.buffer,
        resume.mimetype,
        "resume",
        resume.originalname
    );

    const transcriptUpload = await UploadToCloudinary(
        transcript.buffer,
        transcript.mimetype,
        "transcript",
        transcript.originalname
    );

    const aiResult = await CallAiService({
        resume_url : resumeUpload.publicUrl,
        job_text : post.description,
        // ว่าง/null = ไม่ส่ง → AI ใช้ค่ายที่ตั้งไว้ในหน้าตั้งค่าของ exe (หรือ gemini)
        model_provider: post.model_provider || undefined,
        faculty_match: post.faculty,
        job_title : post.title
    });

    const memberResult = await CreateMember(
        userId,
        postId
    );

    const memberId = memberResult.insertId;

    const hardSkills = Array.isArray(aiResult.data.skills?.hard)
        ? aiResult.data.skills.hard.join(", ")
        : JSON.stringify(aiResult.data.skills?.hard || "");

    const analysis = `
        skills : ${hardSkills}
        Storytelling_score : ${aiResult.data.storytelling_score}
        ai_reason : ${aiResult.data.ai_reason}
        overall_confidence : ${aiResult.data.overall_confidence}
    `.trim();

    const data = {
        memberId : memberId,
        resumeUrl : resumeUpload.publicUrl,
        transcriptUrl : transcriptUpload.publicUrl,
        aiScore : aiResult.data.matching_score,
        skills : `${aiResult.data.skills?.hard ?? ""}`,
        storytelling_score : aiResult.data.storytelling_score,
        ai_reason : aiResult.data.ai_reason,
        overall_confidence : aiResult.data.overall_confidence,
        specific_strengths : aiResult.data.specific_strengths,
        faculty_match : aiResult.data.faculty_match,
        resume_quality_score : aiResult.data.resume_quality_score,
        recommendation_reason : aiResult.data.recommendation_reason
    }

    await CreateResume(data);

    return {
        message: "Apply resume succeed",
        score: aiResult.data.matching_score,
        analysis: analysis
    };
};

export const GetMyApplicationResultService = async (id) => {
    const data = await GetMyApplicationResultModel(id)

    return {
        message : 'Get my application',
        data : data
    }
}
