from flask import Flask,redirect,url_for,render_template,request,flash,abort,session,send_file
from flask_session import Session
from key import secret_key,salt1,salt2
'''import flask_excel as excel'''
from stoken import token
from cmail import sendmail
from itsdangerous import URLSafeTimedSerializer
import mysql.connector
import os
from io import BytesIO
app=Flask(__name__)
app.secret_key=secret_key
app.config['SESSION_TYPE']='filesystem'
Session(app)
'''excel.init_excel(app)'''
#mydb=mysql.connector.connect(host='localhost',user='root',password='14122002',db='ms')
db= os.environ['RDS_DB_NAME']
user=os.environ['RDS_USERNAME']
password=os.environ['RDS_PASSWORD']
host=os.environ['RDS_HOSTNAME']
port=os.environ['RDS_PORT']
with mysql.connector.connect(host=host,user=user,password=password,db=db) as conn:
    cursor=conn.cursor(buffered=True)
    cursor.execute('create table if not exists admin(`username` varchar(50) DEFAULT NULL,`email` varchar(70) NOT NULL,`password` varchar(30) DEFAULT NULL,`email_status` enum('confirmed','not confirmed') DEFAULT 'not confirmed',PRIMARY KEY (`email`),UNIQUE KEY `username` (`username`))')
    cursor.execute('create table if not exists emp(ename varchar(50) NOT NULL,empdept varchar(30) NOT NULL,empemail varchar(70) PRIMARY KEY NOT NULL,emppassword varchar(30) NOT NULL, added_by varchar(70))')
    cursor.execute('create table if not exists`task` (`taskid` int NOT NULL,`tasktitle` varchar(100) NOT NULL,`duedate` date NOT NULL,`taskcontent` text NOT NULL, `empemail` varchar(70) NOT NULL,`assignedby` varchar(70) DEFAULT NULL,`status` varchar(60) DEFAULT 'not updated',PRIMARY KEY (`taskid`), FOREIGN KEY (`empemail`) REFERENCES `emp` (`empemail`), FOREIGN KEY (`assignedby`) REFERENCES `admin` (`email`))')
mydb=mysql.connector.connect(host=host,user=user,password=password,db=db)
@app.route('/')
def index():
    return render_template('title.html')
@app.route('/login',methods=['GET','POST'])
def login():
    if session.get('users'):
        return redirect(url_for('home'))
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from admin where username=%s',[username])
        count=cursor.fetchone()[0]
        if count==1:
            cursor.execute('select count(*) from admin where username=%s and password=%s',[username,password])
            p_count=cursor.fetchone()[0]
            if p_count==1:
                session['user']=username
                cursor.execute('select email_status from admin where username=%s',[username])
                status=cursor.fetchone()[0]
                cursor.close()
                if status!='confirmed':
                    return redirect(url_for('inactive'))
                else:
                    return redirect(url_for('home'))
            else:
                cursor.close()
                flash('invalid password')
                return render_template('login.html')
        else:
            cursor.close()
            flash('invalid username')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/inactive')
def inactive():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from admin where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            return redirect(url_for('home'))
        else:
            return render_template('inactive.html')
    else:
        return redirect(url_for('login'))
@app.route('/homepage',methods=['GET','POST'])
def home():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from admin where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            if request.method=='POST':
                result=f"%{request.form['search']}%"
                cursor=mydb.cursor(buffered=True)
                cursor.execute("select taskid,taskcontent from task where  taskid like %s ",[result,username])
                data=cursor.fetchall()
                if len(data)==0:
                    data='empty'
                return render_template('table.html',data=data)
            return render_template('homepage.html')
        else:
            return redirect(url_for('inactive'))
    else:
        return redirect(url_for('login'))
@app.route('/resendconfirmation')
def resend():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from admin where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.execute('select email from admin where username=%s',[username])
        email=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            flash('Email already confirmed')
            return redirect(url_for('home'))
        else:
            subject='Email Confirmation'
            confirm_link=url_for('confirm',token=token(email,salt1),_external=True)
            body=f"Please confirm your mail-\n\n{confirm_link}"
            sendmail(to=email,body=body,subject=subject)
            flash('Confirmation link sent check your email')
            return redirect(url_for('inactive'))
    else:
        return redirect(url_for('login'))
@app.route('/registration',methods=['GET','POST'])
def registration():
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        email=request.form['email']
        cursor=mydb.cursor(buffered=True)
        try:
            cursor.execute('insert into admin (username,password,email) values(%s,%s,%s)',(username,password,email))
        except mysql.connector.IntegrityError:
            flash('Username or email is already in use')
            return render_template('registration.html')
        else:
            mydb.commit()
            cursor.close()
            subject='Email Confirmation'
            confirm_link=url_for('confirm',token=token(email,salt1),_external=True)
            body=f"Thanks for signing up.Follow this link-\n\n{confirm_link}"
            sendmail(to=email,body=body,subject=subject)
            flash('Confirmation link sent check your email')
            return render_template('registration.html')
    return render_template('registration.html')
    
@app.route('/confirm/<token>')
def confirm(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        email=serializer.loads(token,salt=salt1,max_age=360)
    except Exception as e:
        #print(e)
        abort(404,'Link expired')
    else:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from admin where email=%s',[email])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            flash('Email already confirmed')
            return redirect(url_for('login'))
        else:
            cursor=mydb.cursor(buffered=True)
            cursor.execute("update admin set email_status='confirmed' where email=%s",[email])
            mydb.commit()
            flash('Email confirmation success')
            return redirect(url_for('login'))
@app.route('/forget',methods=['GET','POST'])
def forgot():
    if request.method=='POST':
        email=request.form['email']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from admin where email=%s',[email])
        count=cursor.fetchone()[0]
        cursor.close()
        if count==1:
            cursor=mydb.cursor(buffered=True)
            cursor.execute('SELECT email_status from admin where email=%s',[email])
            status=cursor.fetchone()[0]
            cursor.close()
            if status!='confirmed':
                flash('Please Confirm your email first')
                return render_template('forgot.html')
            else:
                subject='Forget Password'
                confirm_link=url_for('reset',token=token(email,salt=salt2),_external=True)
                body=f"Use this link to reset your password-\n\n{confirm_link}"
                sendmail(to=email,body=body,subject=subject)
                flash('Reset link sent check your email')
                return redirect(url_for('login'))
        else:
            flash('Invalid email id')
            return render_template('forgot.html')
    return render_template('forgot.html')
@app.route('/reset/<token>',methods=['GET','POST'])
def reset(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        email=serializer.loads(token,salt=salt2,max_age=180)
    except:
        abort(404,'Link Expired')
    else:
        if request.method=='POST':
            newpassword=request.form['npassword']
            confirmpassword=request.form['cpassword']
            if newpassword==confirmpassword:
                cursor=mydb.cursor(buffered=True)
                cursor.execute('update admin set password=%s where email=%s',[newpassword,email])
                mydb.commit()
                flash('Reset Successful')
                return redirect(url_for('login'))
            else:
                flash('Passwords mismatched')
                return render_template('newpassword.html')
        return render_template('newpassword.html')

@app.route('/logout')
def logout():
    if session.get('user'):
        session.pop('user')
        return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))
@app.route('/userregistration',methods=['POST','GET'])
def userregistration():
    if session.get('user'):
       if request.method=='POST':
           username=request.form['ename']
           department=request.form['empdept']
           useremail=request.form['empemail']
           password=request.form['emppassword']
           cursor=mydb.cursor(buffered=True)
           try:
              cursor.execute('insert into emp (ename,empdept,empemail,emppassword) values(%s,%s,%s,%s)',[username,department,useremail,password])
           except mysql.connector.IntegrityError:
               flash('an error')
               return render_template('userregistration.html')
           else:
                mydb.commit()
                cursor.close()
                flash('emp registration is success')
                subject='username and password'
                body=f"username and password for login\n\n{username,password}"
                sendmail(to=useremail,body=body,subject=subject)
                flash('mail send to')

           return redirect(url_for('userregistration'))
       return render_template('userregistration.html') 
    else:
        return redirect(url_for('login')) 
@app.route('/dashboard',methods=['GET','POST'])
def dashboard():
    if session.get('user'):
       '''username=session.get('user')
       cursor=mydb.cursor(buffered=True)
       cursor.execute("select taskid,tasktitle,duedate,empemail,taskcontent  from task where email=%s ",[username])
       data=cursor.fetchall()
       cursor.close()'''
       return render_template('table.html')
    else:
        return redirect(url_for('login'))    
@app.route('/addtask',methods=['POST','GET'])
def addtask():
    if session.get('user'):
       if request.method=='POST':
           taskid=request.form['taskid']
           taskname=request.form['tasktitle']
           duedate=request.form['duedate']
           email=request.form['empemail']
           content=request.form['taskcontent']
           cursor=mydb.cursor(buffered=True)
           cursor.execute('insert into task (taskid,tasktitle,duedate,empemail,taskcontent) values(%s,%s,%s,%s,%s)',[taskid,taskname,duedate,email,content])
           mydb.commit()
           cursor.close()
           flash('Task Assigned')
           subject='Task Assigned'
           body=f"duedate and task\n\n{duedate,content}"
           sendmail(to=email,body=body,subject=subject)
           flash('mail send to EMP')

           return redirect(url_for('addtask'))
       return render_template('addtask.html') 
    else:
        return redirect(url_for('login'))
@app.route('/emplogin',methods=['GET','POST'])
def emplogin():
    if session.get('users'):
        return redirect(url_for('emphome'))
    if request.method=='POST':
        username=request.form['ename']
        password=request.form['emppassword']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from emp where ename=%s',[username])
        count=cursor.fetchone()[0]
        if count==1:
            cursor.execute('select count(*) from emp where ename=%s and emppassword=%s',[username,password])
            p_count=cursor.fetchone()[0]
            if p_count==1:
                session['user']=username
                cursor.execute('select count(*) from emp where ename=%s',[username])
                status=cursor.fetchone()[0]
                cursor.close()
                return redirect(url_for('emphome'))
            else:
                cursor.close()
                flash('invalid password')
                return render_template('emplogin.html')
        else:
            cursor.close()
            flash('invalid username')
            return render_template('emplogin.html')
    return render_template('emplogin.html') 
@app.route('/emphomepage',methods=['GET','POST'])
def emphome():
    if session.get('user'):
        return render_template('emphomepage.html')
    else:
        return redirect(url_for('emplogin'))
@app.route('/viewnotes')
def viewnotes():
    if session.get('user'):
       username=session.get('user')
       cursor=mydb.cursor(buffered=True)
       cursor.execute('select bin_to_uuid(nid) as uid,title,date from notes where added_by=%s order by date desc',[username])
       data=cursor.fetchall()
       cursor.close()
       return render_template('table.html',data=data)
    else:
        return redirect(url_for('login'))
@app.route('/emplogout')
def emplogout():
    if session.get('user'):
        session.pop('user')
        return redirect(url_for('emplogin'))
    else:
        return redirect(url_for('emplogin')) 
@app.route('/nid/<uid>')
def vnid(uid):
    if session.get('user'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select bin_to_uuid(nid),title,content,date from notes where bin_to_uuid(nid)=%s',[uid])
        cursor.close()
        uid,title,content,date=cursor.fetchone()
        return render_template('viewnotes.html',title=title,content=content,date=date)
    else:
        return redirect(url_for('login'))
@app.route('/delete/<user>')
def delete(user):
    if session.get('user'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('delete from task where taskid=%s',[user])
        mydb.commit()
        cursor.close()
        flash('task deleted successfully')
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))
    
@app.route('/update/<user>',methods=['GET','POST'])
def update(user):
    if session.get('user'):
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select taskid,tasktitle,duedate,taskcontent,status from task where taskid=%s',[uid])
        uid,title,content =cursor.fetchone()
        cursor.close()
        if request.method=='POST':
            taskid=request.form['taskid']
            tasktitle=request.form['tasktitle']
            duedate=request.form['duedate']
            taskcontent=request.form['taskcontent']
            status=request.form['status']
            cursor=mydb.cursor(buffered=True)
            cursor.execute('update task set taskid=%s,tasktitle=%s,duedate=%s,taskcontent=%s,status=%s where taskid=%s',[taskid,tasktitle,duedate,taskcontent,status,user])
            mydb.commit()
            cursor.close()
            flash('task upated successfully')
            return redirect(url_for('dashboard'))
        return render_template('update.html',taskid=taskid,tasktitle=tasktitle,duedate=duedate,taskcontent=taskcontent,status=status)
    else:
        return redirect(url_for('login')) 
if __name__=="__main__":
   app.run()