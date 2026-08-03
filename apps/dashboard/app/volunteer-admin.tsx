"use client";

import { Check, Database, MapPinned, RefreshCw, Route, ShieldAlert, X } from "lucide-react";
import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type ReportStatus = "pending" | "approved" | "rejected";
type TaskStatus = "open" | "claimed" | "submitted" | "verified" | "cancelled";

type VolunteerReport = {
  id: string;
  categoryLabel: string;
  cleanupReasonLabel: string;
  description: string;
  address: string;
  lat: number;
  lng: number;
  photoUrl: string;
  status: ReportStatus;
  priority: "low" | "normal" | "urgent";
  reviewNote: string;
  createdAt: string;
  reporter: { email: string; displayName: string };
};

type VolunteerTask = {
  id: string;
  obstacleId: string;
  title: string;
  description: string;
  categoryLabel: string;
  address: string;
  priority: "low" | "normal" | "urgent";
  status: TaskStatus;
  assigneeId?: string;
  assigneeName?: string;
  assigneeEmail?: string;
  completionNote: string;
  reviewNote: string;
  photoUrl: string;
  updatedAt: string;
};

type OperationsSummary = {
  reports: Partial<Record<ReportStatus, number>>;
  tasks: Partial<Record<TaskStatus, number>>;
  obstacles: Record<string, number>;
  consistent: boolean;
  issueCount: number;
  generatedAt: string;
};

const reportLabels: Record<ReportStatus, string> = { pending: "待审核", approved: "已通过", rejected: "已驳回" };
const taskLabels: Record<TaskStatus, string> = { open: "待认领", claimed: "已认领", submitted: "待复核", verified: "已完成", cancelled: "已取消" };

async function adminJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    cache: "no-store",
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body = await response.json().catch(() => null) as { detail?: string } | null;
  if (!response.ok) throw new Error(body?.detail || `HTTP ${response.status}`);
  return body as T;
}

export function VolunteerAdminView() {
  const [tab, setTab] = useState<"reports" | "tasks">("reports");
  const [reportStatus, setReportStatus] = useState<ReportStatus>("pending");
  const [taskStatus, setTaskStatus] = useState<"all" | TaskStatus>("all");
  const [reports, setReports] = useState<Record<ReportStatus, VolunteerReport[]>>({ pending: [], approved: [], rejected: [] });
  const [tasks, setTasks] = useState<VolunteerTask[]>([]);
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const loadSequence = useRef(0);

  const load = useCallback(async (silent = false) => {
    const sequence = ++loadSequence.current;
    if (!silent) setLoading(true);
    if (!silent) setErrors([]);
    const results = await Promise.allSettled([
      adminJson<{ items: VolunteerReport[] }>("/api/v1/admin/reports?status=pending"),
      adminJson<{ items: VolunteerReport[] }>("/api/v1/admin/reports?status=approved"),
      adminJson<{ items: VolunteerReport[] }>("/api/v1/admin/reports?status=rejected"),
      adminJson<{ items: VolunteerTask[] }>("/api/v1/admin/tasks"),
      adminJson<OperationsSummary>("/api/v1/admin/operations/summary"),
    ]);
    const names = ["待审核上报", "已通过上报", "已驳回上报", "公共任务", "一致性摘要"];
    const nextErrors: string[] = [];
    results.forEach((result, index) => {
      if (result.status === "rejected") nextErrors.push(`${names[index]}加载失败：${result.reason instanceof Error ? result.reason.message : "未知错误"}`);
    });
    if (sequence !== loadSequence.current) return;
    const [pendingResult, approvedResult, rejectedResult, taskResult, summaryResult] = results;
    if (pendingResult.status === "fulfilled") setReports((value) => ({ ...value, pending: pendingResult.value.items }));
    if (approvedResult.status === "fulfilled") setReports((value) => ({ ...value, approved: approvedResult.value.items }));
    if (rejectedResult.status === "fulfilled") setReports((value) => ({ ...value, rejected: rejectedResult.value.items }));
    if (taskResult.status === "fulfilled") setTasks(taskResult.value.items);
    if (summaryResult.status === "fulfilled") setSummary(summaryResult.value);
    setErrors(nextErrors);
    setLoading(false);
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(() => void load(), 0);
    const timer = window.setInterval(() => void load(true), 4000);
    const onVisibility = () => { if (document.visibilityState === "visible") void load(true); };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("focus", onVisibility);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("focus", onVisibility);
    };
  }, [load]);

  const reviewReport = async (report: VolunteerReport, action: "approve" | "reject") => {
    const note = window.prompt(action === "approve" ? "审核备注（可留空）" : "请输入驳回原因") ?? "";
    if (action === "reject" && note.trim().length < 2) return;
    setLoading(true);
    try {
      await adminJson(`/api/v1/admin/reports/${encodeURIComponent(report.id)}`, {
        method: "PATCH",
        body: JSON.stringify({ action, note, publishTask: action === "approve", priority: report.priority }),
      });
      await load();
    } catch (cause) {
      setErrors([`审核提交失败：${cause instanceof Error ? cause.message : "请稍后重试"}`]);
      setLoading(false);
    }
  };

  const reviewTask = async (task: VolunteerTask, action: "verify" | "return" | "cancel" | "reopen") => {
    const prompts = {
      verify: "复核备注（可留空）",
      return: "请输入退回原因",
      cancel: "请输入取消派单原因",
      reopen: "请输入重新发布说明（可留空）",
    };
    const note = window.prompt(prompts[action]) ?? "";
    if ((action === "return" || action === "cancel") && note.trim().length < 2) return;
    setLoading(true);
    try {
      await adminJson(`/api/v1/admin/tasks/${encodeURIComponent(task.id)}`, {
        method: "PATCH",
        body: JSON.stringify({ action, note }),
      });
      await load();
    } catch (cause) {
      setErrors([`任务操作失败：${cause instanceof Error ? cause.message : "请检查当前状态"}`]);
      setLoading(false);
    }
  };

  const reportCounts = {
    pending: summary?.reports.pending ?? reports.pending.length,
    approved: summary?.reports.approved ?? reports.approved.length,
    rejected: summary?.reports.rejected ?? reports.rejected.length,
  };
  const taskCounts = {
    open: summary?.tasks.open ?? tasks.filter((item) => item.status === "open").length,
    claimed: summary?.tasks.claimed ?? tasks.filter((item) => item.status === "claimed").length,
    submitted: summary?.tasks.submitted ?? tasks.filter((item) => item.status === "submitted").length,
    verified: summary?.tasks.verified ?? tasks.filter((item) => item.status === "verified").length,
    cancelled: summary?.tasks.cancelled ?? tasks.filter((item) => item.status === "cancelled").length,
  };
  const taskTotal = Object.values(taskCounts).reduce((total, count) => total + count, 0);
  const visibleTasks = useMemo(() => taskStatus === "all" ? tasks : tasks.filter((item) => item.status === taskStatus), [taskStatus, tasks]);

  return <div className="subpage admin-page">
    <div className="subpage-head"><div><span className="eyebrow">VOLUNTEER OPERATIONS</span><h1>志愿者审核与公共派单</h1><p>手机上报、审核入库、地图障碍和 App 公共任务使用同一条状态链。</p></div><div className="admin-head-actions"><span className="architecture-badge"><ShieldAlert size={15} />管理员认证保护</span><button className="secondary-action" onClick={() => void load()}><RefreshCw size={15} className={loading ? "spin" : ""} />刷新</button></div></div>

    <div className="admin-source-note panel"><Database size={16} /><span><strong>数据口径：</strong>监管首页“活动事件”包含边缘设备识别事件；这里“公共派单”只统计审核通过并发布给志愿者的任务，两者不是同一个指标。</span></div>
    <div className="admin-summary-grid">
      <div className="panel"><span>待审核上报</span><strong>{reportCounts.pending}</strong></div>
      <div className="panel"><span>待认领任务</span><strong>{taskCounts.open}</strong></div>
      <div className="panel"><span>处理中</span><strong>{taskCounts.claimed + taskCounts.submitted}</strong></div>
      <div className={`panel consistency-${summary?.consistent === false ? "bad" : "good"}`}><span>状态链一致性</span><strong>{summary ? (summary.consistent ? "正常" : `${summary.issueCount} 项异常`) : "检查中"}</strong></div>
    </div>

    <div className="admin-tabs"><button className={tab === "reports" ? "active" : ""} onClick={() => setTab("reports")}>上报审核 <em>{reportCounts.pending}</em></button><button className={tab === "tasks" ? "active" : ""} onClick={() => setTab("tasks")}>公共派单 <em>{taskTotal}</em></button></div>
    {errors.map((error) => <div className="admin-error panel" key={error}><ShieldAlert size={15} />{error}</div>)}

    {tab === "reports" && <>
      <div className="filter-row admin-filters">{(["pending", "approved", "rejected"] as const).map((status) => <button key={status} className={reportStatus === status ? "active" : ""} onClick={() => setReportStatus(status)}>{reportLabels[status]} {reportCounts[status]}</button>)}</div>
      <div className="review-list">
        {!loading && reports[reportStatus].length === 0 && <div className="panel admin-empty"><Check size={24} /><strong>当前没有{reportLabels[reportStatus]}上报</strong><span>新的手机上报会自动出现在这里。</span></div>}
        {reports[reportStatus].map((report) => <article className="panel review-card" key={report.id}>
          <Image className="review-photo" src={report.photoUrl} alt={report.categoryLabel} width={320} height={200} unoptimized />
          <div className="review-copy"><div className="review-title"><span className={`priority priority-${report.priority}`}>{({ low: "低", normal: "普通", urgent: "紧急" })[report.priority]}</span><h2>{report.categoryLabel}</h2><small>{new Date(report.createdAt).toLocaleString("zh-CN")}</small></div><p>{report.description}</p><div className="review-meta"><span><MapPinned size={14} />{report.address}</span><span><ShieldAlert size={14} />{report.cleanupReasonLabel}</span><span>上报人：{report.reporter.displayName}（{report.reporter.email}）</span><span>编号：{report.id}</span></div>{report.reviewNote && <div className="review-note">审核说明：{report.reviewNote}</div>}</div>
          {report.status === "pending" && <div className="review-actions"><button className="secondary-action danger-action" onClick={() => void reviewReport(report, "reject")}><X size={15} />驳回</button><button className="primary-action" onClick={() => void reviewReport(report, "approve")}><Check size={15} />通过并派单</button></div>}
        </article>)}
      </div>
    </>}

    {tab === "tasks" && <>
      <div className="filter-row admin-filters"><button className={taskStatus === "all" ? "active" : ""} onClick={() => setTaskStatus("all")}>全部 {taskTotal}</button>{(["open", "claimed", "submitted", "verified", "cancelled"] as const).map((status) => <button key={status} className={taskStatus === status ? "active" : ""} onClick={() => setTaskStatus(status)}>{taskLabels[status]} {taskCounts[status]}</button>)}</div>
      <div className="review-list">
        {!loading && visibleTasks.length === 0 && <div className="panel admin-empty"><Route size={24} /><strong>当前没有{taskStatus === "all" ? "公共" : taskLabels[taskStatus]}任务</strong><span>上报审核通过并发布后会自动生成任务。</span></div>}
        {visibleTasks.map((task) => <article className="panel task-review-card" key={task.id}><div className="task-review-icon"><Route size={20} /></div><div className="review-copy"><div className="review-title"><span className={`task-state task-state-${task.status}`}>{taskLabels[task.status]}</span><h2>{task.title}</h2><small>{task.id}</small></div><p>{task.description}</p><div className="review-meta"><span><MapPinned size={14} />{task.address}</span><span>障碍编号：{task.obstacleId}</span>{task.assigneeId && <span>认领人：{task.assigneeName || task.assigneeId}{task.assigneeEmail ? `（${task.assigneeEmail}）` : ""}</span>}{task.completionNote && <span>处置说明：{task.completionNote}</span>}</div>{task.reviewNote && <div className="review-note">后台说明：{task.reviewNote}</div>}</div>
          {task.status === "submitted" && <div className="review-actions"><a className="secondary-action" href={`/api/v1/admin/tasks/${encodeURIComponent(task.id)}/evidence`} target="_blank" rel="noreferrer">查看凭证</a><button className="secondary-action danger-action" onClick={() => void reviewTask(task, "return")}><X size={15} />退回</button><button className="primary-action" onClick={() => void reviewTask(task, "verify")}><Check size={15} />确认闭环</button></div>}
          {task.status === "cancelled" && <div className="review-actions"><button className="primary-action" onClick={() => void reviewTask(task, "reopen")}><RefreshCw size={15} />重新发布</button></div>}
        </article>)}
      </div>
    </>}
  </div>;
}
