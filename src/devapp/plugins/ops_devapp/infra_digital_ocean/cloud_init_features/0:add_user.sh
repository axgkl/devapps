adduser $user
cp -a /root/.ssh /home/$user/
chown -R $user /home/$user/.ssh
echo "$user	ALL=(ALL)	NOPASSWD: ALL" >>/etc/sudoers
