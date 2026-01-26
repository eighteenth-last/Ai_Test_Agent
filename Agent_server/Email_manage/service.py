from typing import List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import os
import resend
import requests
import hmac
import hashlib
import base64
import json


class EmailService:
    """邮件发送服务"""
    
    @staticmethod
    def send_email(
        contact_ids: List[int],
        subject: str,
        html_content: str,
        email_type: str = 'custom',
        db: Session = None
    ) -> Dict[str, Any]:
        """
        通用邮件发送方法
        
        Args:
            contact_ids: 联系人ID列表（从contacts表动态获取）
            subject: 邮件主题
            html_content: HTML格式的邮件内容
            email_type: 邮件类型 (report/bug/custom)
            db: Database session
        
        Returns:
            发送结果
        """
        try:
            from database.connection import Contact, EmailRecord, EmailConfig
            
            active_config = db.query(EmailConfig).filter(EmailConfig.is_active == 1).first()
            
            if not active_config:
                print("[EmailService] 未找到激活的邮件配置")
                return {
                    "success": False,
                    "message": "未找到激活的邮件配置，请在邮件配置页面激活后重试"
                }
            else:
                provider = (active_config.provider or "").strip().lower()
                sender_email = active_config.sender_email
                test_mode = bool(active_config.test_mode)
                test_email = active_config.test_email
                
                if provider not in ["aliyun", "resend"]:
                    return {
                        "success": False,
                        "message": f"当前不支持的邮件服务商类型: {active_config.provider}"
                    }
                
                if provider == "resend":
                    resend.api_key = active_config.api_key
                
                print(f"[EmailService] 使用数据库配置: {active_config.config_name} (服务商: {provider}, 测试模式: {test_mode})")
            
            # 2. 从contacts表动态获取联系人信息
            contacts = db.query(Contact).filter(Contact.id.in_(contact_ids)).all()
            
            if not contacts:
                return {
                    "success": False,
                    "message": "未找到指定的联系人"
                }
            
            # 3. 发送邮件给每个联系人
            sent_count = 0
            failed_contacts = []
            sent_ids = []
            recipients_list = []
            
            for contact in contacts:
                try:
                    # 检查测试模式
                    recipient_email = test_email if test_mode else contact.email
                    
                    if provider == "aliyun":
                        response = EmailService._send_aliyun_email(
                            access_key=active_config.api_key,
                            secret_key=active_config.secret_key,
                            sender_email=sender_email,
                            to_email=recipient_email,
                            subject=subject,
                            html_content=html_content
                        )
                        email_id = response.get('RequestId', 'unknown')
                    else:
                        response = resend.Emails.send({
                            "from": sender_email,
                            "to": recipient_email,
                            "subject": subject,
                            "html": html_content
                        })
                        email_id = response.get('id', 'unknown')
                    
                    sent_count += 1
                    sent_ids.append(email_id)
                    recipients_list.append({
                        "name": contact.name,
                        "email": recipient_email,
                        "original_email": contact.email if test_mode else None,
                        "status": "success",
                        "test_mode": test_mode
                    })
                    
                    if test_mode:
                        print(f"[EmailService] ✓ [测试模式] 邮件已发送给: {contact.name} (目标: {contact.email} → 实际: {test_email}) - ID: {email_id}")
                    else:
                        print(f"[EmailService] ✓ 邮件已发送给: {contact.name} ({contact.email}) - ID: {email_id}")
                    
                except Exception as email_error:
                    error_msg = str(email_error)
                    print(f"[EmailService] ✗ 发送给 {contact.name} 失败: {error_msg}")
                    
                    failed_contacts.append({
                        "name": contact.name,
                        "email": contact.email,
                        "error": error_msg
                    })
                    recipients_list.append({
                        "name": contact.name,
                        "email": contact.email,
                        "status": "failed",
                        "error": error_msg
                    })
            
            # 4. 保存发送记录到数据库
            try:
                if sent_count == len(contacts):
                    record_status = "success"
                elif sent_count > 0:
                    record_status = "partial"
                else:
                    record_status = "failed"
                
                email_record = EmailRecord(
                    subject=subject,
                    recipients=recipients_list,
                    status=record_status,
                    success_count=sent_count,
                    failed_count=len(failed_contacts),
                    total_count=len(contacts),
                    email_type=email_type,
                    content_summary=f"发送给 {len(contacts)} 位联系人",
                    email_ids=sent_ids if sent_ids else None,
                    failed_details=failed_contacts if failed_contacts else None
                )
                
                db.add(email_record)
                db.commit()
                db.refresh(email_record)
                
                print(f"[EmailService] 📝 发送记录已保存 (ID: {email_record.id})")
                
            except Exception as db_error:
                print(f"[EmailService] ⚠️ 保存发送记录失败: {db_error}")
            
            # 5. 返回结果
            if sent_count == len(contacts):
                return {
                    "success": True,
                    "message": f"邮件已成功发送给 {sent_count} 位联系人",
                    "data": {
                        "sent_count": sent_count,
                        "total_count": len(contacts),
                        "recipients": recipients_list,
                        "email_ids": sent_ids
                    }
                }
            elif sent_count > 0:
                return {
                    "success": True,
                    "message": f"邮件已发送给 {sent_count}/{len(contacts)} 位联系人，{len(failed_contacts)} 位失败",
                    "data": {
                        "sent_count": sent_count,
                        "total_count": len(contacts),
                        "failed": failed_contacts,
                        "email_ids": sent_ids
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "所有邮件发送失败",
                    "data": {
                        "failed": failed_contacts
                    }
                }
            
        except Exception as e:
            import traceback
            print(f"[EmailService] 发送邮件失败: {e}")
            print(traceback.format_exc())
            return {
                "success": False,
                "message": f"发送邮件失败: {str(e)}"
            }
    
    
    @staticmethod
    def _send_aliyun_email(access_key: str, secret_key: str, sender_email: str, 
                           to_email: str, subject: str, html_content: str) -> Dict[str, Any]:
        """
        使用阿里云邮件推送服务发送邮件
        
        Args:
            access_key: 阿里云 Access Key ID
            secret_key: 阿里云 Access Key Secret
            sender_email: 发件人邮箱
            to_email: 收件人邮箱
            subject: 邮件主题
            html_content: HTML格式的邮件内容
            
        Returns:
            阿里云API响应
        """
        import urllib.parse
        import uuid
        
        # 阿里云邮件推送API endpoint
        endpoint = "https://dm.aliyuncs.com/"
        
        # 构建请求参数
        params = {
            "Action": "SingleSendMail",
            "AccountName": sender_email,
            "ReplyToAddress": "false",
            "AddressType": "1",
            "ToAddress": to_email,
            "Subject": subject,
            "HtmlBody": html_content,
            "Format": "JSON",
            "Version": "2015-11-23",
            "AccessKeyId": access_key,
            "SignatureMethod": "HMAC-SHA1",
            "Timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "SignatureVersion": "1.0",
            "SignatureNonce": str(uuid.uuid4()),
            "RegionId": "cn-hangzhou"
        }
        
        # 计算签名
        sorted_params = sorted(params.items())
        query_string = "&".join([f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}" 
                                 for k, v in sorted_params])
        string_to_sign = f"GET&%2F&{urllib.parse.quote(query_string, safe='')}"
        
        h = hmac.new((secret_key + "&").encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1)
        signature = base64.b64encode(h.digest()).decode('utf-8')
        
        params["Signature"] = signature
        
        # 发送请求
        response = requests.get(endpoint, params=params, timeout=30)
        result = response.json()
        
        if response.status_code != 200 or "Code" in result:
            raise Exception(f"阿里云邮件发送失败: {result.get('Message', '未知错误')}")
        
        return result
    
    
    @staticmethod
    def send_to_auto_receive_bug_contacts(
        subject: str,
        html_content: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        发送邮件给所有开启了"自动接收BUG"的联系人
        
        Args:
            subject: 邮件主题
            html_content: HTML格式的邮件内容
            db: Database session
        
        Returns:
            发送结果
        """
        try:
            from database.connection import Contact
            
            # 查询所有开启自动接收BUG的联系人
            auto_contacts = db.query(Contact).filter(Contact.auto_receive_bug == 1).all()
            
            if not auto_contacts:
                return {
                    "success": False,
                    "message": "没有开启自动接收BUG的联系人"
                }
            
            # 获取联系人ID列表
            contact_ids = [c.id for c in auto_contacts]
            
            # 调用通用发送方法
            return EmailService.send_email(
                contact_ids=contact_ids,
                subject=subject,
                html_content=html_content,
                email_type='bug',
                db=db
            )
            
        except Exception as e:
            return {
                "success": False,
                "message": f"发送失败: {str(e)}"
            }
