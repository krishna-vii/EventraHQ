"use client";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { api, Notice, Shell } from "../../../components/marketplace";
export default function Confirmation() {
 const [error,setError]=useState("");
 const started=useRef(false);
 useEffect(()=>{if(started.current)return;started.current=true;const q=new URLSearchParams(location.search);const token_hash=q.get('token_hash');const type=q.get('type');if(!token_hash||!type){setError('This confirmation link is incomplete. Request a new email.');return;}history.replaceState(null,'','/auth/confirm');api<{authenticated:boolean}>('/auth/verify',{token_hash,type}).then(r=>{if(r.authenticated)location.replace('/account?tab=profile');else setError('Verification completed without a session. Please log in.');}).catch(e=>setError(e.message));},[]);
 return <Shell><div className="container narrow page-intro"><h1>Let’s get you connected.</h1>{error?<><Notice error>{error}</Notice><Link className="button" href="/login">Return to login</Link></>:<p role="status">Verifying your email link…</p>}</div></Shell>;
}
