# Show the OS name without changing the network hostname.
case $- in
*i*)
    fre3nder_os_name=$(. /etc/os-release; printf '%s' "$NAME")
    export PS1='\u@'"$fre3nder_os_name"'\$ '
    unset fre3nder_os_name
    ;;
esac
